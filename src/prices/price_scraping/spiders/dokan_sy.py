"""
Dokan (Syria) — https://www.dokan.sy/.

A diaspora-facing gift/remittance platform ("your bridge to your loved ones
in Syria" — mobile top-ups, money transfer via Sham Cash, flowers, sweets,
electronics, and groceries delivered to any Syrian governorate). Runs the
same "AIZ"-branded Laravel storefront template already scaffolded for
souqmy_ye (identical `/search2` listing AJAX, identical `aiz-card-box`
product markup, identical `showAddToCartModal(<id>)` id marker).

    GET /search2?min_price=&max_price=&keyword=&sort_by=&page=<N>&categories[]=<id>
    -> {"success", "total_product_count", "product_html", "pagination_html"}

No CSRF token or cookie required — confirmed with a cookie-less curl_cffi
request. `product_html` is a raw HTML fragment (one `div.aiz-card-box` per
product), parsed with a `scrapy.Selector`.

Scoped to `categories[]=66` — "market dukkan" (سوبر ماركت / groceries), the
site's grocery/provisions category, confirmed by page <title> ("سوبر ماركت
دكان | تسوق المواد الغذائية والتموينية مع توصيل في سوريا") and by category
listing showing food items (fresh milk, etc). The wider site is a
multi-category gift shop (top-ups, flowers, electronics) — NOT food-led —
so this spider is deliberately scoped to the food category only, same
pattern as tsaooq_sy's category=19 scoping.

Verified live 2026-09-01: total_product_count=254 for category 66. Page 1
and page 2 returned disjoint product-id sets (24 cards each, zero overlap)
confirming genuine pagination, not a homepage-carousel undercount.

Currency: prices render as "$X.XX" (USD) directly in the card markup — this
is a diaspora-paid platform, so USD pricing (not SYP) is expected and
matches what's on the page, not countries.yaml's SYP default.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.dokan.sy"
GROCERY_CATEGORY_ID = 66
MAX_PAGES = 20  # safety cap; category has 254 items across ~11 pages of 24
_ADD_CART_RE = re.compile(r"showAddToCartModal\((\d+)\)")
_DIGITS_RE = re.compile(r"[^\d.]")


class DokanSySpider(scrapy.Spider):
    name = "dokan_sy"
    allowed_domains = ["dokan.sy", "www.dokan.sy"]
    currency = "USD"
    language = "ar"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield self._api_request(1)

    def _api_request(self, page):
        return scrapy.Request(
            f"{BASE_URL}/search2?min_price=&max_price=&keyword=&sort_by=&page={page}"
            f"&categories%5B%5D={GROCERY_CATEGORY_ID}",
            callback=self.parse_api,
            errback=self.errback,
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json, text/javascript, */*; q=0.01",
            },
            meta={"page": page},
            dont_filter=True,
        )

    def parse_api(self, response):
        page = response.meta["page"]
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON from {response.url}")
            return

        html = data.get("product_html") or ""
        cards = scrapy.Selector(text=html).css("div.aiz-card-box") if html else []
        found = 0

        for card in cards:
            name = (card.css("h3 a::attr(title)").get() or "").strip()
            url = card.css("h3 a::attr(href)").get() or ""
            price_text = card.css("span.text-primary::text").get() or ""
            price = _DIGITS_RE.sub("", price_text) if price_text else ""
            match = _ADD_CART_RE.search(card.get())
            pid = match.group(1) if match else ""
            if not name or not price or not pid:
                continue
            found += 1
            yield {
                "product_id": pid,
                "product_name": name[:500],
                "category": "",
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": url or response.url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        logger.info(
            f"{self.name}: page={page} cards={len(cards)} yielded={found} "
            f"total_product_count={data.get('total_product_count')}"
        )

        if cards and page < MAX_PAGES:
            yield self._api_request(page + 1)

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
