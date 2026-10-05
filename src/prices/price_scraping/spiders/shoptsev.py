"""Price-bearing physical consumer goods from ShopTSV, Liberia."""

import re
from datetime import datetime, timezone

import scrapy
from scrapy_playwright.page import PageMethod


_START_URL = "https://shoptsev.com/shop"
_PRODUCT_SEL = 'a[href^="/product/"]'
_PRICE_RE = re.compile(r"\$\s*([\d,]+(?:\.\d{1,2})?)")


def _parse_usd(text: str) -> str | None:
    match = _PRICE_RE.search(text or "")
    if not match:
        return None
    amount = match.group(1).replace(",", "")
    return amount if float(amount) > 0 else None


class ShoptsevSpider(scrapy.Spider):
    name = "shoptsev"
    allowed_domains = ["shoptsev.com"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2,
    }

    async def start(self):
        yield scrapy.Request(
            _START_URL,
            callback=self.parse_listing,
            meta={
                "playwright": True,
                "playwright_page_goto_kwargs": {"wait_until": "domcontentloaded"},
                "playwright_page_methods": [
                    PageMethod("wait_for_selector", _PRODUCT_SEL, timeout=30000),
                    PageMethod("wait_for_timeout", 1000),
                ],
            },
        )

    def parse_listing(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        seen: set[str] = set()

        for anchor in response.css(_PRODUCT_SEL):
            href = anchor.attrib.get("href", "")
            product_id = href.removeprefix("/product/").split("?", 1)[0]
            text = " ".join(part.strip() for part in anchor.css("::text").getall() if part.strip())
            price = _parse_usd(text)
            name = (anchor.css("img::attr(alt)").get() or "").split(" — view", 1)[0].strip()

            # Exclude concepts, arrivals, and quote-only rows that do not offer
            # a current, purchasable item price.
            unavailable = "arriving soon" in text.lower() or "concept" in name.lower()
            excluded_listing = product_id.startswith(("test-", "qa-")) or any(
                token in name.lower() for token in ("benz ", "toyota ", "vehicle")
            )
            if (
                not product_id
                or not name
                or not price
                or unavailable
                or excluded_listing
                or product_id in seen
            ):
                continue
            seen.add(product_id)
            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "category": None,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": response.urljoin(href),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
