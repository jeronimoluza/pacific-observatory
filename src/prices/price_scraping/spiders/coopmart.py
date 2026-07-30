"""
Spider for Co.opmart Online (Vietnam) - https://cooponline.vn/

Root cause of prior near-zero fresh-food coverage (2026-07-30): cooponline.vn
is a Next.js SSR shell whose category pages (e.g. /c/rau-cu-trai-cay) always
render only the first ~40 products server-side, regardless of category size
(rau-cu-trai-cay has 1060 items across 27 pages; thit-trung-hai-san has ~495
across 13). The `page` query param is canonicalized away — the server 301s
`?page=2` back to the bare URL — and there is no <a href> pagination link in
the HTML for a CrawlSpider to follow; deeper pages are fetched entirely
client-side via a POST to discovery.tekoapis.com. So the previous
CrawlSpider (LinkExtractor over `--s\\d+` product links, no pagination rule)
only ever saw each category's first ~40 products, most of which were the
site's default-sorted/promoted items rather than the long tail of fresh
produce, meat, and seafood SKUs.

Fix: call the same discovery API the storefront's own JS uses
(POST /api/v2/search-skus-v2, no auth/session required — verified via curl)
directly, walking all pages per category instead of scraping rendered HTML.
"""

import json
import logging
import math

import scrapy

logger = logging.getLogger(__name__)


class CoopmartSpider(scrapy.Spider):
    name = "coopmart"
    allowed_domains = ["discovery.tekoapis.com"]
    currency = "VND"

    API_URL = "https://discovery.tekoapis.com/api/v2/search-skus-v2"
    TERMINAL_ID = 26607
    PAGE_SIZE = 40
    CATEGORY_SLUGS = [
        "/c/rau-cu-trai-cay",  # fresh produce: vegetables, tubers, fruit (01.1.6/01.1.7)
        "/c/thit-trung-hai-san",  # meat, eggs, seafood (01.1.2/01.1.3)
        "/c/sua-san-pham-tu-sua",  # milk & dairy
    ]

    HEADERS = {
        "Content-Type": "application/json",
        "Accept-Language": "vi",
        "Referer": "https://cooponline.vn/",
        "Origin": "https://cooponline.vn",
    }

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 0.5,
    }

    def _body(self, slug, page):
        return json.dumps(
            {
                "terminalId": self.TERMINAL_ID,
                "page": page,
                "pageSize": self.PAGE_SIZE,
                "slug": slug,
                "filter": {},
                "sorting": {
                    "sort": "SORT_BY_UNSPECIFIED",
                    "order": "ORDER_BY_UNSPECIFIED",
                },
                "returnFilterable": [],
                "isNeedFeaturedProducts": False,
            }
        )

    def _api_request(self, slug, page):
        return scrapy.Request(
            self.API_URL,
            method="POST",
            headers=self.HEADERS,
            body=self._body(slug, page),
            callback=self.parse_page,
            meta={"slug": slug, "page": page},
        )

    async def start(self):
        for slug in self.CATEGORY_SLUGS:
            yield self._api_request(slug, 1)

    def parse_page(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error(f"coopmart: JSON decode failed for {slug} page {page}")
            return

        data = payload.get("data") or {}
        products = data.get("products") or []
        total = data.get("total") or 0
        logger.info(
            f"coopmart: slug={slug} page={page} items={len(products)} total={total}"
        )

        for p in products:
            item = self._parse_product(p, response)
            if item:
                yield item

        total_pages = math.ceil(total / self.PAGE_SIZE) if total else 0
        if page < total_pages:
            yield self._api_request(slug, page + 1)

    def _parse_product(self, p, response):
        canonical = p.get("canonical")
        product_name = p.get("name")
        price = p.get("latestPrice") or p.get("supplierRetailPrice")

        if not product_name or not price or not canonical:
            return None

        categories = p.get("categories") or []
        category = (
            " > ".join(c.get("name") for c in categories if c.get("name")) or None
        )

        return {
            "product_id": p.get("sku"),
            "product_name": product_name,
            "price": price,
            "currency": self.currency,
            "category": category,
            "url": f"https://cooponline.vn/{canonical}",
            "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
        }
