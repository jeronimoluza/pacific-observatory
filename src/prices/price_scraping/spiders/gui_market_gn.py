"""Gui Market Guinea catalog rendered through Playwright."""

import logging
import re
from datetime import datetime, timezone

import scrapy
from scrapy_playwright.page import PageMethod

logger = logging.getLogger(__name__)

_START_URL = "https://gui-market.com/recherche?sort=popularity"
_NAME_SEL = '.details a[href^="/product/"] h3[title]'
_PRICE_RE = re.compile(r"([\d\s\u00a0\u202f,.]+)\s*GNF\b", re.IGNORECASE)
_SLUG_RE = re.compile(r"^/product/([^/?#]+)")


def _parse_price(text: str) -> str | None:
    match = _PRICE_RE.search(text or "")
    if not match:
        return None
    amount = re.sub(r"[\s\u00a0\u202f,]", "", match.group(1)).rstrip(".")
    return amount if amount.isdigit() and int(amount) > 0 else None


class GuiMarketGnSpider(scrapy.Spider):
    name = "gui_market_gn"
    allowed_domains = ["gui-market.com"]
    currency = "GNF"
    language = "fr"

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
                    PageMethod("wait_for_selector", _NAME_SEL, timeout=20000),
                    PageMethod("wait_for_timeout", 1200),
                ],
            },
        )

    def parse_listing(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        seen: set[str] = set()
        yielded = 0

        for name_node in response.css(_NAME_SEL):
            anchor = name_node.xpath("parent::a[1]")
            href = anchor.attrib.get("href", "")
            id_match = _SLUG_RE.match(href)
            if not id_match:
                continue
            product_id = id_match.group(1)
            if product_id in seen:
                continue

            card = name_node.xpath(
                "ancestor::div[div[contains(concat(' ', normalize-space(@class), ' '), ' image-holder ')]][1]"
            )
            if not card:
                continue
            # The old/list price is nested under <del>; direct span text gives
            # the current price before the promotional message.
            price_texts = card.css("div.details span::text").getall()
            price = None
            for text in price_texts:
                price = _parse_price(text)
                if price:
                    break
            name = (name_node.attrib.get("title") or name_node.css("::text").get() or "").strip()
            if not name or not price:
                continue

            seen.add(product_id)
            yielded += 1
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

        logger.info("gui_market_gn: yielded=%d", yielded)
