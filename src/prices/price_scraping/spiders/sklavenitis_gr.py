"""
Sklavenitis — https://www.sklavenitis.gr/ (Greece's largest supermarket chain).

Server-rendered "Atcom Yoda" storefront (no JS execution needed). Category
tree is walked from /katigories/, which links ~140 two-segment leaf category
paths (e.g. /freska-froyta-lachanika/lachanika/) spanning the full grocery
assortment (fresh produce, meat, fish, dairy, frozen, wine/beer, grocery
staples, snacks, baby, pet food, household).

Each leaf category page renders 24 product cards per page inside
`div.product` blocks. Every card carries a `data-plugin-analyticsimpressions`
attribute -- an HTML-entity-encoded JSON blob with a clean, pre-parsed
{item_id, item_name, item_category, price} for that single product (price is
already a float in EUR, matching the rendered "main-price", so there is no
regex-on-markup or minor-unit risk). The product PDP URL comes from the
sibling `a.absLink::attr(href)`.

Pagination trap (same shape as the ?page=N / ?pg=N zero-indexed trap in the
skill brief): `?page=N` is silently ignored and re-serves page 1. The real
parameter is `?pg=N` (1-indexed), and the *only* reliable way to know when to
stop is the page's own forward-pagination widget:
`<section class="pagination go-next" data-pg="N">` where N is the next page
to fetch, and data-pg="" (empty) on the last page. Verified on a 102-item
category: pg=1..4 return 24 items each, pg=5 returns the remaining 6, and the
go-next widget's data-pg goes 2,3,4,5,"" -- distinct-id total across all 5
pages == 102, matching the site's own "24 από τα 102 προϊόντα" counter.
"""

import html
import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.sklavenitis.gr"
START_URL = f"{BASE_URL}/katigories/"

# Non-catalog sections under /katigories/ that are not two-segment product
# leaves at all (about/account/help pages use the same href shape).
_EXCLUDE_PREFIXES = ("/about/", "/account/", "/voitheia-agoron/")


class SklavenitisGrSpider(scrapy.Spider):
    name = "sklavenitis_gr"
    allowed_domains = ["sklavenitis.gr"]
    currency = "EUR"
    language = "el"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(START_URL, callback=self.parse_index, errback=self.errback)

    def parse_index(self, response):
        hrefs = set()
        for href in response.css("a::attr(href)").getall():
            if href.startswith(_EXCLUDE_PREFIXES):
                continue
            parts = href.strip("/").split("/")
            if len(parts) == 2 and all(parts):
                hrefs.add(href if href.startswith("/") else f"/{href}")

        hrefs = sorted(hrefs)
        logger.info(f"{self.name}: leaf categories found={len(hrefs)}")
        for href in hrefs:
            yield response.follow(
                href,
                callback=self.parse_listing,
                errback=self.errback,
            )

    def parse_listing(self, response):
        cards = response.css("div.product")
        found = 0

        for card in cards:
            raw = card.attrib.get("data-plugin-analyticsimpressions")
            href = card.css("a.absLink::attr(href)").get()
            if not raw or not href:
                continue

            try:
                payload = json.loads(html.unescape(raw))
                item = payload["Call"]["ecommerce"]["items"][0]
            except (ValueError, KeyError, IndexError, TypeError):
                continue

            name = (item.get("item_name") or "").strip()
            price = item.get("price")
            product_id = item.get("item_id")
            if not name or price is None or not product_id:
                continue
            if float(price) == 0:
                continue

            found += 1
            yield {
                "product_id": str(product_id),
                "product_name": name[:500],
                "category": item.get("item_category") or "",
                "price": str(price),
                "currency": self.currency,
                "available": True,
                "url": response.urljoin(href),
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        logger.info(f"{self.name}: {response.url} cards={len(cards)} yielded={found}")

        next_pg = response.css("section.pagination.go-next::attr(data-pg)").get()
        if next_pg:
            next_url = response.urljoin(f"{response.url.split('?')[0]}?pg={next_pg}")
            yield response.follow(
                next_url,
                callback=self.parse_listing,
                errback=self.errback,
            )

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
