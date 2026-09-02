"""
MegaMarche (Côte d'Ivoire) — https://www.megamarche.ci/.

Custom storefront. Category pages server-render only the first tranche of
cards, and the deeper catalog is served by a lazy-load JSON endpoint:

    GET /api/shop/products/next/<CATEGORY_CODE>/<OFFSET>
    -> {"products": [{"pid","b","t","p","pl","av",...}],
        "totalNbProducts": N, "nextId": <next offset or null>}

The second path segment is a 1-BASED OFFSET, not a page number. Walking it
as a page counter (1, 2, 3, ...) slides the window forward by a single
product per request: a measured walk of "pages" 1-9 returned 324 rows
containing only 44 distinct products. The endpoint hands back the correct
next offset in `nextId` (1 -> 37 -> 73 -> ..., step 36) and returns
nextId=null on the final tranche, so the walk follows that cursor.

The endpoint requires an XHR-shaped request: a Referer on the matching
/mes-courses/<slug>/<code> category page plus X-Requested-With. Without
them it answers 400/404 and returns a zero-byte body.

Category codes are discovered by crawling /mes-courses/<slug>/<CODE> links
from the homepage down; the tree is ~76 codes across 7 top departments,
mixing food (supermarche and its 27 subcategories) with electronics and
DIY, so the classifier sees a wide catalog.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.megamarche.ci"
_CAT_RE = re.compile(r"/mes-courses/([a-z0-9\-]+)/([A-Z0-9]{8})")
_DIGITS_RE = re.compile(r"[^\d]")


class MegamarcheCiSpider(scrapy.Spider):
    name = "megamarche_ci"
    allowed_domains = ["megamarche.ci"]
    currency = "XOF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.4,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_codes: set[str] = set()

    async def start(self):
        yield scrapy.Request(
            f"{BASE_URL}/", callback=self.parse_categories, errback=self.errback
        )

    def parse_categories(self, response):
        """Collect category codes, recurse into new ones, walk each via the API."""
        for slug, code in _CAT_RE.findall(response.text):
            if code in self.seen_codes:
                continue
            self.seen_codes.add(code)
            path = f"/mes-courses/{slug}/{code}"
            # Deeper subcategories are only linked from the category page.
            yield response.follow(
                path, callback=self.parse_categories, errback=self.errback
            )
            yield self._api_request(code, slug, 1)

        logger.info(f"{self.name}: categories discovered so far={len(self.seen_codes)}")

    def _api_request(self, code, slug, offset):
        return scrapy.Request(
            f"{BASE_URL}/api/shop/products/next/{code}/{offset}",
            callback=self.parse_api,
            errback=self.errback,
            headers={
                "Referer": f"{BASE_URL}/mes-courses/{slug}/{code}",
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json, text/javascript, */*; q=0.01",
            },
            meta={"code": code, "slug": slug, "offset": offset},
            dont_filter=True,
        )

    def parse_api(self, response):
        code, slug = response.meta["code"], response.meta["slug"]
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON from {response.url}")
            return

        products = data.get("products") or []
        for product in products:
            name = " ".join(
                part for part in (product.get("b"), product.get("t")) if part
            ).strip()
            price = _DIGITS_RE.sub("", product.get("p") or "")
            if not name or not price:
                continue
            slug_part = product.get("pl") or ""
            pid = product.get("pid") or ""
            yield {
                "product_id": pid,
                "product_name": name[:500],
                "category": slug,
                "price": price,
                "currency": self.currency,
                "available": bool(product.get("av", True)),
                "url": f"{BASE_URL}/{slug_part}/{pid}/p"
                if slug_part and pid
                else response.url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        logger.info(
            f"{self.name}: category={slug} offset={response.meta['offset']} "
            f"got={len(products)} total={data.get('totalNbProducts')}"
        )

        next_id = data.get("nextId")
        # Follow the server's cursor only; a synthesised counter re-serves a
        # window offset by one product and never terminates.
        if products and next_id and next_id != response.meta["offset"]:
            yield self._api_request(code, slug, next_id)

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
