"""
Spider for Aldi Ireland -- https://www.aldi.ie/ (storefront:
https://groceries.aldi.ie/ / https://www.aldi.ie/, Nuxt SPA).

The triage sheet's GOTCHA claimed "limited online range, aggregators report
only ~247 SKUs" (i.e. SpecialBuys-only, no real groceries) -- checked
directly and this is WRONG: `asl.api.aldi.ie/commerce/v2/
product-category-tree` (open, no auth) lists a full grocery taxonomy
(Fresh Food, Food Cupboard, Chilled Food, Alcohol, Drinks, Frozen Food,
Bakery, Health & Beauty, Baby & Toddler, Pet Care, ...) alongside
SpecialBuys, and category listing pages
(`https://www.aldi.ie/<top-slug>/<leaf-slug>`) are server-rendered Tier 1A
HTML with a real price directly in the markup -- no API call needed at
scrape time.

Verified live 2026-09-06: category `specialbuys` tile
`id="product-tile-000000000633728001"`, brand LACURA, name "Lip Balm",
`.base-price__regular` = "€4.49". Spider walks the leaf categories from
the category-tree API (stride-sampled) and parses product tiles directly
off each listing page -- no pagination observed on SpecialBuys-style
grids (single page per leaf), consistent with Aldi's curated/limited
per-category range.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_CATEGORY_TREE_URL = (
    "https://asl.api.aldi.ie/commerce/v2/product-category-tree"
    "?serviceType=walk-in&servicePoint=D105"
)
_TILE_ID_RE = re.compile(r'id="product-tile-(\d+)"')
_TILE_BLOCK_RE = re.compile(
    r'id="product-tile-(\d+)"(.*?)</a>', re.S
)
_NAME_RE = re.compile(r'product-tile__name"[^>]*><p[^>]*>([^<,]+)')
_BRAND_RE = re.compile(r'product-tile__brandname"[^>]*><p[^>]*>([^<,]+)')
_PRICE_RE = re.compile(r'base-price__regular"[^>]*><span>([^<]+)</span>')
_CATEGORY_STRIDE = 4  # sample every Nth leaf category


def _flatten_leaves(nodes, prefix=""):
    leaves = []
    for node in nodes:
        children = node.get("children") or []
        if children:
            leaves.extend(_flatten_leaves(children))
        else:
            leaves.append((node.get("name"), node.get("urlSlugText"), node.get("key")))
    return leaves


class AldiIeSpider(scrapy.Spider):
    name = "aldi_ie"
    allowed_domains = ["aldi.ie"]
    currency = "EUR"
    language = "en"

    IMPERSONATE_PROFILE = "chrome124"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
            "price_scraping.middlewares.CustomUserAgentMiddleware": None,
        },
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_TIMEOUT": 30,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            _CATEGORY_TREE_URL,
            callback=self.parse_category_tree,
            meta={"impersonate": self.IMPERSONATE_PROFILE},
            headers={"Accept": "application/json"},
        )

    def parse_category_tree(self, response):
        try:
            data = response.json()
        except json.JSONDecodeError:
            logger.warning("aldi_ie: category tree not JSON")
            return
        nodes = data.get("data") or []
        leaves = _flatten_leaves(nodes)
        sampled = leaves[::_CATEGORY_STRIDE]
        logger.info("aldi_ie: sampled %d/%d leaf categories", len(sampled), len(leaves))
        for name, slug, key in sampled:
            if not slug or not key:
                continue
            yield scrapy.Request(
                f"https://www.aldi.ie/products/{slug}/k/{key}",
                callback=self.parse_category,
                meta={"impersonate": self.IMPERSONATE_PROFILE, "category": name},
            )

    def parse_category(self, response):
        category = response.meta["category"]
        body = response.text
        n_found = 0
        for m in _TILE_BLOCK_RE.finditer(body):
            sku, block = m.group(1), m.group(2)
            name_m = _NAME_RE.search(block)
            price_m = _PRICE_RE.search(block)
            if not name_m or not price_m:
                continue
            price_text = price_m.group(1).strip()
            price_val = re.sub(r"[^\d.,]", "", price_text).replace(",", ".")
            if not price_val:
                continue
            brand_m = _BRAND_RE.search(block)
            name = name_m.group(1).strip()
            if brand_m:
                name = f"{brand_m.group(1).strip()} {name}"
            n_found += 1
            yield {
                "product_id": sku,
                "product_name": name[:500],
                "category": category,
                "price": price_val,
                "currency": self.currency,
                "available": True,
                # DuplicationPipeline dedups on item["url"]; one listing page
                # yields many products, so a unique #fragment per sku is
                # required or all but the first product on the page vanish.
                "url": f"{response.url}#{sku}",
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        logger.info("aldi_ie: %s -> %d products", response.url, n_found)
