"""
Spider for Cold Storage (Singapore) - https://www.coldstorage.com.sg/

Cold Storage's storefront is a Next.js App Router site. The /search endpoint
returns React Server Component (RSC) payloads when called with `RSC: 1`, which
embed product JSON inline. We hit `?q=<term>` for a fixed list of CPI staples
and regex-extract product objects from the streamed body. No auth, no CF.

Caveats:
  - RSC payload is a streamed chunk format, not regular JSON. Robust parsing
    requires regex extraction of `{"productId":..,"name":..,"price":..}` shapes
    rather than json.loads on the body.
  - Each search returns up to 30 results; we use a curated list of CPI staples
    so the union covers grocery, fresh, and household. To grow coverage, extend
    SEARCH_TERMS.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE_URL = "https://coldstorage.com.sg/search"
_PRODUCT_URL_BASE = "https://coldstorage.com.sg/product"

# CPI-relevant staple search terms. Each returns up to 30 products; the union
# covers most of the basket. Extend as needed.
SEARCH_TERMS = [
    "rice",
    "milk",
    "bread",
    "egg",
    "chicken",
    "pork",
    "beef",
    "fish",
    "vegetable",
    "fruit",
    "noodle",
    "pasta",
    "oil",
    "sugar",
    "salt",
    "flour",
    "butter",
    "cheese",
    "yoghurt",
    "biscuit",
    "snack",
    "tea",
    "coffee",
    "juice",
    "water",
    "soda",
    "tofu",
    "sauce",
    "soup",
    "cereal",
    "shampoo",
    "soap",
    "toothpaste",
    "tissue",
    "detergent",
]


# Product object shape inside RSC payload: nested in `"initialProducts":[...]`,
# each entry has integer productId, name, slug, price (number), promoPrice, etc.
# Extract via a tolerant regex then json.loads each candidate.
_PRODUCT_BLOB_RE = re.compile(
    r'\{"productId":\d+,"name":"(?:\\.|[^"\\])*","slug":"[^"]*","price":[\d.]+[^{}]*?\}'
)


class ColdStorageSgSpider(scrapy.Spider):
    name = "cold_storage_sg"
    allowed_domains = ["coldstorage.com.sg"]
    country = "singapore"
    currency = "SGD"
    language = "en"

    custom_settings = {
        "DOWNLOAD_DELAY": 1.5,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "CONCURRENT_REQUESTS": 4,
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "text/x-component, */*",
            "RSC": "1",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        },
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scraped_product_ids = set()

    def start_requests(self):
        for term in SEARCH_TERMS:
            yield scrapy.Request(
                f"{_BASE_URL}?q={term}&limit=30",
                callback=self.parse_search,
                meta={"term": term},
            )

    def parse_search(self, response):
        term = response.meta["term"]

        candidates = _PRODUCT_BLOB_RE.findall(response.text)
        if not candidates:
            logger.info("No products in RSC stream for term=%s", term)
            return

        scraped_at = response.headers.get(
            "Date",
            datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT").encode(),
        ).decode("utf-8")

        emitted = 0
        for blob in candidates:
            try:
                obj = json.loads(blob)
            except json.JSONDecodeError:
                continue

            product_id = str(obj.get("productId", ""))
            if not product_id or product_id in self.scraped_product_ids:
                continue
            self.scraped_product_ids.add(product_id)

            product_name = obj.get("name", "")
            price = obj.get("price")
            slug = obj.get("slug") or obj.get("handle") or product_id
            category = obj.get("category") or term

            if not product_name or price is None:
                continue

            yield {
                "product_id": product_id,
                "product_name": product_name,
                "price": str(price),
                "currency": self.currency,
                "category": category,
                "url": f"{_PRODUCT_URL_BASE}/{slug}",
                "scraped_at": scraped_at,
            }
            emitted += 1

        logger.info("term=%s emitted=%d (raw_blobs=%d)", term, emitted, len(candidates))
