"""
Spider for Kingfoodmart (kingfoodmart.com) - premium HCMC fresh-food
supermarket chain built on a Next.js storefront over the Onelife/Kariba
commerce backend.

The category grid is client-hydrated, but Next.js serves the same payload
server-side. Each top-level category slug resolves to
/_next/data/<buildId>/<slug>.json?page=N returning
props.pageProps.categoryData with a paginated `products` list plus a
`pagination.last_page`. The buildId is read from the homepage __NEXT_DATA__
so it survives redeploys.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://kingfoodmart.com"
_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


class KingfoodmartSpider(scrapy.Spider):
    name = "kingfoodmart"
    allowed_domains = ["kingfoodmart.com"]
    currency = "VND"
    language = "vi"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
        "DEFAULT_REQUEST_HEADERS": {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/json",
        },
    }

    async def start(self):
        yield scrapy.Request(_BASE + "/", callback=self.parse_home)

    def parse_home(self, response):
        m = _NEXT_DATA_RE.search(response.text)
        if not m:
            logger.error("kingfoodmart: no __NEXT_DATA__ on home page")
            return
        data = json.loads(m.group(1))
        build_id = data.get("buildId")
        tree = data["props"]["pageProps"].get("categoryTree") or []
        slugs = [
            c.get("slug")
            for c in tree
            if c.get("level") == 1 and c.get("slug") and c.get("children")
        ]
        if not build_id or not slugs:
            logger.error("kingfoodmart: missing buildId or category slugs")
            return
        for slug in slugs:
            yield self._category_request(build_id, slug, 1)

    def _category_request(self, build_id, slug, page):
        url = f"{_BASE}/_next/data/{build_id}/{slug}.json?page={page}"
        return scrapy.Request(
            url,
            callback=self.parse_category,
            meta={"build_id": build_id, "slug": slug, "page": page},
            headers={"Accept": "application/json"},
        )

    def parse_category(self, response):
        meta = response.meta
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error(
                "kingfoodmart: non-JSON for %s p%d", meta["slug"], meta["page"]
            )
            return

        cat = (payload.get("pageProps") or {}).get("categoryData") or {}
        products = cat.get("products") or []
        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in products:
            item = self._parse_product(p, meta["slug"], scraped_at)
            if item:
                yield item

        pagination = cat.get("pagination") or {}
        last = pagination.get("last_page") or 1
        if meta["page"] < last:
            yield self._category_request(
                meta["build_id"], meta["slug"], meta["page"] + 1
            )

    def _parse_product(self, p, slug, scraped_at):
        name = p.get("name")
        price = p.get("discountPrice") or p.get("originalPrice")
        if not name or not price:
            return None
        prod_slug = p.get("slug")
        return {
            "product_id": p.get("id"),
            "product_name": name,
            "price": price,
            "currency": self.currency,
            "category": p.get("subCate") or slug,
            "url": f"{_BASE}/{prod_slug}" if prod_slug else _BASE,
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
