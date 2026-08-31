"""
SPAR Zimbabwe — https://www.spar.co.zw/.

Server-rendered ASP.NET storefront. The product-detail route
(/products/<id>/<slug>) returns a shell with no name or price, so the
category *listing* cards are the extraction surface: each <li> under
.product-listing carries the name (.listing-details p), the price
(.product-links strong, HTML-entity encoded as "USD&#36;4.00") and the
canonical product href.

Catalog is walked as 12 departments -> 181 subdepartments, each paginated
with ?pg=N (zero-indexed). Pagination is followed via the rendered
".paging a.next" href rather than a synthesised counter — ?page=N is
silently ignored and re-serves page 1, which would look like a small
catalog instead of a broken walk.

Zimbabwe is dollarised; the storefront quotes USD by default and offers ZWG
through a client-side currency switcher, so the server HTML is USD.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.spar.co.zw"
START_URL = f"{BASE_URL}/products"

# "USD$4.00" / "$4.00" / "ZWG$120.00" -> ("USD", "4.00")
_PRICE_RE = re.compile(r"([A-Z]{3})?\s*\$\s*([\d,]+(?:\.\d{1,2})?)")
_PRODUCT_ID_RE = re.compile(r"/products/(\d+)/")


class SparZwSpider(scrapy.Spider):
    name = "spar_zw"
    allowed_domains = ["spar.co.zw"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(START_URL, callback=self.parse_index, errback=self.errback)

    def parse_index(self, response):
        hrefs = sorted(
            set(
                response.css('a[href*="/products/subdepartment/"]::attr(href)').getall()
            )
        )
        logger.info(f"{self.name}: subdepartments found={len(hrefs)}")
        for href in hrefs:
            slug = href.rstrip("/").rsplit("/", 1)[-1]
            yield response.follow(
                href,
                callback=self.parse_listing,
                errback=self.errback,
                meta={"category": slug},
            )

    def parse_listing(self, response):
        category = response.meta["category"]
        cards = response.css(".product-listing li")
        found = 0

        for card in cards:
            name = (card.css(".listing-details p::text").get() or "").strip()
            raw_price = (card.css(".product-links strong::text").get() or "").strip()
            href = card.css(".listing-image a::attr(href)").get() or ""
            if not name or not raw_price:
                continue

            match = _PRICE_RE.search(raw_price)
            if not match:
                continue
            currency, amount = match.group(1) or self.currency, match.group(2)
            amount = amount.replace(",", "")
            if float(amount) == 0:
                continue

            id_match = _PRODUCT_ID_RE.search(href)
            found += 1
            yield {
                "product_id": id_match.group(1) if id_match else "",
                "product_name": name[:500],
                "category": category,
                "price": amount,
                "currency": currency,
                "available": True,
                "url": response.urljoin(href) if href else response.url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        logger.info(
            f"{self.name}: {response.url} category={category} "
            f"cards={len(cards)} yielded={found}"
        )

        next_href = response.css(".paging a.next::attr(href)").get()
        if next_href:
            yield response.follow(
                next_href,
                callback=self.parse_listing,
                errback=self.errback,
                meta={"category": category},
            )

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
