"""Spider for METRO Slovakia -- https://sortiment.metro.sk/.

METRO is a cash-and-carry wholesale chain; its Slovak storefront
(`sortiment.metro.sk`) is a JS-rendered SPA with no product data in the raw
HTML. A Playwright network trace of a category page found a two-endpoint
JSON API that is fully anonymous -- no login/session needed to see prices,
unlike many B2B wholesale sites:

  GET /searchdiscover/articlesearch/search
      ?storeId=00021&language=sk-SK&country=SK&query=*&rows=100&page=<N>
      &filter=category:potraviny
      -> {"amount": 13889, "totalPages": 139, "resultIds": [...],
          "results": {"<variantId>": {"price": 10.76, "isAvailable": true}}}
      (page N and page N-1 confirmed disjoint id sets -- real pagination,
      not a repeated fixed page)

  GET /evaluate.article.v1/betty-variants
      ?storeIds=00021&ids=<variantId>&ids=<variantId>...&country=SK&locale=sk-SK
      -> {"result": {"<articleId>": {"variants": {"<variantSuffix>":
            {"description": "...", "categories": [{"levels": [...]}]}}}}}
      (name + category breadcrumb; batches confirmed to work with 100 ids
      in one call)

storeId=00021 is one specific physical METRO store (Bratislava-area); this
pipeline's single-city convention applies the same way it does for
darkstore chains like goodwill_ge / globus_online_kg. Store 00021 was the
default store returned by the site with no location cookie set.

No currency field in either payload -- METRO SK is a single-country,
EUR-only storefront (countries.yaml confirms EUR for slovak_republic), so
this is not an inferred-from-symbol case (rule 11): there is no symbol in
the JSON to infer from, only the fact that this API serves exactly one
country.

Filter to `category:potraviny` (Food) -- METRO's B2B catalog also includes
a large non-food ("nepotravinovy-tovar": gastro equipment, cleaning
chemicals, electronics) side; scoping to the food filter keeps this run
food-and-beverage-led per the sweep's scope, though `coicop_classification:
classifier` still runs per-product as usual (no per-item COICOP
short-circuit).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urlencode

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://sortiment.metro.sk"
_STORE_ID = "00021"
_ROWS = 100
_VARIANT_BATCH = 30  # keeps the betty-variants URL under Scrapy's URLLENGTH_LIMIT
_BATCH_HEADERS = {"Referer": f"{_BASE}/"}


def _chunks(seq: list[str], size: int) -> list[list[str]]:
    return [seq[i : i + size] for i in range(0, len(seq), size)]


class MetroSkSpider(scrapy.Spider):
    name = "metro_sk"
    allowed_domains = ["sortiment.metro.sk"]
    currency = "EUR"
    language = "sk"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 5,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def _search_url(self, page: int) -> str:
        qs = urlencode(
            {
                "storeId": _STORE_ID,
                "language": "sk-SK",
                "country": "SK",
                "query": "*",
                "rows": _ROWS,
                "page": page,
                "filter": "category:potraviny",
            }
        )
        return f"{_BASE}/searchdiscover/articlesearch/search?{qs}"

    def _variants_url(self, ids: list[str]) -> str:
        parts = [
            ("storeIds", _STORE_ID),
            ("country", "SK"),
            ("locale", "sk-SK"),
        ] + [("ids", i) for i in ids]
        qs = urlencode(parts)
        return f"{_BASE}/evaluate.article.v1/betty-variants?{qs}"

    async def start(self):
        yield scrapy.Request(
            self._search_url(1),
            callback=self.parse_search,
            headers=_BATCH_HEADERS,
            meta={"impersonate": "chrome124", "page": 1},
        )

    def parse_search(self, response):
        page = response.meta["page"]
        data = response.json()
        results = data.get("results", {})
        ids = [
            vid for vid, r in results.items() if r.get("isAvailable") and r.get("price")
        ]
        total_pages = data.get("totalPages", page)
        logger.info(f"metro_sk: page={page}/{total_pages} n={len(ids)}")

        if not ids:
            if page < total_pages:
                yield scrapy.Request(
                    self._search_url(page + 1),
                    callback=self.parse_search,
                    headers=_BATCH_HEADERS,
                    meta={"impersonate": "chrome124", "page": page + 1},
                )
            return

        batches = _chunks(ids, _VARIANT_BATCH)
        for i, batch in enumerate(batches):
            yield scrapy.Request(
                self._variants_url(batch),
                callback=self.parse_variants,
                headers=_BATCH_HEADERS,
                meta={
                    "impersonate": "chrome124",
                    "page": page,
                    "total_pages": total_pages,
                    "prices": results,
                    "is_last_batch": i == len(batches) - 1,
                },
            )

    def parse_variants(self, response):
        page = response.meta["page"]
        total_pages = response.meta["total_pages"]
        prices = response.meta["prices"]

        data = response.json().get("result", {})
        scraped_at = datetime.now(timezone.utc).isoformat()

        n_yielded = 0
        for article_id, article in data.items():
            for suffix, variant in (article.get("variants") or {}).items():
                variant_id = variant.get("bettyVariantId", {}).get(
                    "bettyVariantId"
                ) or (article_id + suffix)
                price_info = prices.get(variant_id)
                if not price_info:
                    continue
                price = price_info.get("price")
                name = variant.get("description")
                if not name or price is None:
                    continue
                try:
                    price_val = float(price)
                except (TypeError, ValueError):
                    continue
                if price_val <= 0:
                    continue

                categories = variant.get("categories") or []
                category = None
                if categories:
                    levels = categories[0].get("levels") or []
                    if levels:
                        category = levels[-1].get("displayName")
                    else:
                        category = categories[0].get("name")

                name = re.sub(r"\s+", " ", str(name)).strip()

                n_yielded += 1
                yield {
                    "product_id": variant_id,
                    "product_name": name[:500],
                    "category": category,
                    "price": str(price_val),
                    "currency": self.currency,
                    "url": f"{_BASE}/shop/product/{variant_id}",
                    "language": self.language,
                    "scraped_at_utc": scraped_at,
                }

        logger.info(f"metro_sk: page={page} yielded={n_yielded}")

        if response.meta.get("is_last_batch") and page < total_pages:
            yield scrapy.Request(
                self._search_url(page + 1),
                callback=self.parse_search,
                headers=_BATCH_HEADERS,
                meta={"impersonate": "chrome124", "page": page + 1},
            )
