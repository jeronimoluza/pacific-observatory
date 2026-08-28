"""
Spider for OpenSooq Egypt (eg.opensooq.com) -- consumer-goods classifieds.

OpenSooq is a multi-country classifieds network with a per-country
subdomain (af/dz/bh/eg/jo/sa/... .opensooq.com — 22+ countries). Egypt was
picked as the one country to ship: `eg.opensooq.com` serves a real,
independently-priced EGP catalog (confirmed via the page's own
`countryObject` -> {"abbreviation":"eg","currency_en":"EGP","name_english":
"Egypt"}), and among the shard's four candidate countries (Afghanistan,
Algeria, Bahrain, Egypt) Egypt is the largest population/economy and the
deepest catalog to crawl.

Category pages embed a clean schema.org ItemList inside a single
`<script type="application/ld+json">{"@context":...,"@graph":[...]}` block
— NOT a bare top-level ItemList, it's nested one level down inside
`@graph`. Each `ItemList.itemListElement[].item` is a full Product with
`offers.price`/`priceCurrency`/`availability`. Confirmed live 2026-08-17 on
/en/electronics -> 30 real EGP-priced Products (e.g. EGP 4500 for a TV).

Pagination is `?page=N` (confirmed live: page 2 returns 30 different
listing IDs). Scoped to consumer-goods categories only — cars, real estate
and jobs are excluded as out of scope for a retail price basket.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://eg.opensooq.com"
_CATEGORIES = [
    "electronics",
    "electronics-appliances",
    "household-appliances",
    "mobile-phones-tablets",
    "computers-and-laptops",
    "gaming-consoles",
    "fashion-and-kids",
    "home-garden",
    "beauty-and-health",
    "books-and-hobbies",
    "food-suppliments",
]
# Bench 2026-08-17 (smoke, cap=10): 120 items over 5 requests in 10.8s at
# CONCURRENT_REQUESTS_PER_DOMAIN=8 (~2.16s/request) -- 10 pages/category was
# far under budget. Raised to 100; worst case (all 11 categories hit the
# cap) is 1,100 requests, ~5min at the observed per-request cost, well
# inside the 25min budget. Each category still self-limits via the
# `if n > 0` check below once its real page depth is exhausted.
MAX_PAGES = 100

_LDJSON_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
    re.DOTALL,
)


class OpensooqEgSpider(scrapy.Spider):
    name = "opensooq_eg"
    allowed_domains = ["opensooq.com"]
    currency = "EGP"
    language = "ar"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
        "DOWNLOAD_DELAY": 0.2,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        for slug in _CATEGORIES:
            yield scrapy.Request(
                f"{_BASE}/en/{slug}",
                callback=self.parse_listing,
                meta={"slug": slug, "page": 1},
            )

    def parse_listing(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]
        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for raw in _LDJSON_RE.findall(response.text):
            data = self._loads(raw)
            if not isinstance(data, dict):
                continue
            for node in data.get("@graph") or []:
                if node.get("@type") != "ItemList":
                    continue
                for el in node.get("itemListElement") or []:
                    item = el.get("item") or {}
                    offers = item.get("offers") or {}
                    price = offers.get("price")
                    name = item.get("name")
                    url = item.get("url")
                    if not name or price in (None, "", 0, "0") or not url:
                        continue
                    n += 1
                    yield {
                        "product_id": url.rstrip("/").rsplit("/", 1)[-1],
                        "product_name": str(name).strip()[:500],
                        "category": slug,
                        "price": str(price),
                        "currency": offers.get("priceCurrency") or self.currency,
                        "available": str(offers.get("availability", "")).endswith(
                            "InStock"
                        ),
                        "url": url,
                        "language": self.language,
                        "scraped_at_utc": scraped_at,
                    }
        logger.info(f"{self.name}: {slug} page={page} items={n}")

        if n > 0 and page < MAX_PAGES:
            yield scrapy.Request(
                f"{_BASE}/en/{slug}?page={page + 1}",
                callback=self.parse_listing,
                meta={"slug": slug, "page": page + 1},
            )

    @staticmethod
    def _loads(block):
        try:
            return json.loads(block)
        except (ValueError, TypeError):
            return None
