"""
SouqMy (Yemen) — https://souqmy.com/.

Custom Laravel multi-vendor marketplace. Every page-level route (/, /category/*,
/product/*, even /robots.txt) sits behind an obfuscated JS "checking your
browser" challenge (host header "hcdn") that returns 403 to a plain
curl_cffi request. The listing AJAX endpoint the storefront's own JS calls
to render product grids is NOT behind that challenge and answers 200 with
zero cookies:

    GET /search2?min_price=&max_price=&keyword=&sort_by=&page=<N>
        [&categories[]=<id>]
    -> {"success", "total_product_count", "product_html", "pagination_html"}

`product_html` is a raw HTML fragment (one `div.aiz-card-box` per product)
that is parsed directly with a `scrapy.Selector`. Omitting `categories[]`
returns the whole catalog (verified: 63 distinct product ids across pages
1-3, page 4 empty — matches total_product_count exactly, so pagination
genuinely advances rather than re-serving page 1).

Prices are quoted in Yemeni Rial. The site carries a client-side currency
switcher (`changeCurrency('YER')` = "old" rial vs `changeCurrency('NYER')`
= "new" rial, POSTed to /currency and persisted in the Laravel session
cookie) — confirmed live to change the SAME product's displayed price by
exactly 3x (3,500 -> 10,500). This spider never calls /currency, so it
inherits the server's *default* currency for a cookie-less request, which
is the "old rial" YER code — i.e. the smaller of the two figures. Flagged
here so downstream doesn't assume the price switches over time; it doesn't
change unless the session's currency_code cookie changes.

Catalog is small (63 SKUs) and general merchandise (jewelry, watches,
women's/men's care, small electronics, furniture) — the site has no
food/grocery category, confirmed by decoding the full category-slug list
from the homepage nav.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://souqmy.com"
MAX_PAGES = 30  # safety cap; catalog is ~63 items across ~3 pages
_ADD_CART_RE = re.compile(r"showAddToCartModal\((\d+)\)")
_DIGITS_RE = re.compile(r"[^\d.]")


class SouqmyYeSpider(scrapy.Spider):
    name = "souqmy_ye"
    allowed_domains = ["souqmy.com"]
    currency = "YER"
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
            f"{BASE_URL}/search2?min_price=&max_price=&keyword=&sort_by=&page={page}",
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
            name = (card.css("h3 a::text").get() or "").strip()
            url = card.css("h3 a::attr(href)").get() or ""
            price_text = card.css("span.text-primary::text").get() or ""
            price = _DIGITS_RE.sub("", price_text.split()[0]) if price_text else ""
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
