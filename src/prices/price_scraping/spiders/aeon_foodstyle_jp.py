"""
Spider for AEON Food Style Net Super (Japan) —
https://aeonfoodstyle.netsuper.aeon.com

Per-store catalogue (query param `store_code`); this spider is pinned to
store 0000807570 ("ダイエー南浦和東口店" per the site's own store-name
telemetry — a Daiei-brand AEON Food Style store in Saitama). Different
store_code values almost certainly carry different prices/assortment
(standard for Japanese netsuper); revisit if multi-store coverage is wanted.

The storefront is a Next.js App Router SPA gated behind a store-selection
flow (robots.txt disallows /store-select), so category browsing needs a
session. But the "bestseller" article page (`/articles/<id>`) that the site
itself links from the store landing page calls a plain, unauthenticated JSON
endpoint for its product grid — found via one Playwright network trace,
confirmed reproducible with bare `requests`/curl (no cookies needed):

    GET /api/articles/<page_id>?storeCode=<store_code>&nextParamText=<url-encoded JSON>

`nextParamText` is an opaque-looking but fully static param blob (pageIndex/
pageSize/pageId/moduleType/moduleId/platform/storeCode/tagId) that the page
itself echoes back in each response's `nextParamTextForProducts` field, so
pagination is just incrementing `pageIndex` until `viewParts` (or its
`products` list) comes back empty. Verified 2026-08-11: 87 unique products
across 5 pages for this store's bestseller article (id 43877) before it ran
dry — a curated top-seller subset, not the full catalog (the full category
tree needs the store-selection session, not chased here for a marginal-value
country pass).

Price fields: `price` is pre-tax, `includingTaxPrice` is what the site
displays as "税込<amount>円" — the consumer-facing figure — so that's what
this spider emits.
"""

import json
import logging
import urllib.parse
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

STORE_CODE = "0000807570"
PAGE_ID = 43877
MODULE_ID = "3056212"
PAGE_SIZE = 20
MAX_PAGES = 30


def _api_url(page_index: int) -> str:
    next_param = {
        "pageIndex": page_index,
        "pageSize": PAGE_SIZE,
        "pageId": PAGE_ID,
        "moduleType": 23,
        "loadingId": f"loading:{MODULE_ID}:{page_index - 1}",
        "moduleId": MODULE_ID,
        "platform": "app",
        "storeCode": STORE_CODE,
        "tagId": 0,
    }
    return (
        f"https://aeonfoodstyle.netsuper.aeon.com/api/articles/{PAGE_ID}"
        f"?storeCode={STORE_CODE}&nextParamText={urllib.parse.quote(json.dumps(next_param))}"
    )


class AeonFoodstyleJpSpider(scrapy.Spider):
    name = "aeon_foodstyle_jp"
    allowed_domains = ["aeonfoodstyle.netsuper.aeon.com"]
    currency = "JPY"
    language = "ja"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 0.5,
    }

    def start_requests(self):
        yield scrapy.Request(
            _api_url(1), callback=self.parse_page, meta={"page_index": 1}
        )

    def parse_page(self, response):
        page_index = response.meta["page_index"]
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error(f"aeon_foodstyle_jp: JSON decode failed on page {page_index}")
            return

        view_parts = data.get("viewParts") or []
        if not view_parts:
            logger.info(
                f"aeon_foodstyle_jp: no viewParts at page {page_index}, stopping"
            )
            return

        products = view_parts[0].get("products") or []
        if not products:
            logger.info(
                f"aeon_foodstyle_jp: empty products at page {page_index}, stopping"
            )
            return

        logger.info(f"aeon_foodstyle_jp: page {page_index} -> {len(products)} products")
        for p in products:
            price = p.get("includingTaxPrice") or p.get("price")
            name = p.get("name")
            if not (price and name):
                continue
            product_id = str(p.get("janCode") or p.get("id"))
            yield {
                "product_id": product_id,
                "product_name": str(name).strip()[:500],
                "category": None,
                "price": str(price),
                "currency": self.currency,
                # No per-product PDP route was found in this article-listing flow
                # (see module docstring); the productId query param keeps each
                # row's url unique so DuplicationPipeline's url-based dedup
                # doesn't collapse the whole catalog to one row.
                "url": (
                    f"https://aeonfoodstyle.netsuper.aeon.com/articles/{PAGE_ID}"
                    f"?store_code={STORE_CODE}&productId={product_id}"
                ),
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        if page_index < MAX_PAGES:
            yield scrapy.Request(
                _api_url(page_index + 1),
                callback=self.parse_page,
                meta={"page_index": page_index + 1},
            )
