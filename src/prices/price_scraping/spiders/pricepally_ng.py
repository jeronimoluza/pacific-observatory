"""
Spider for PricePally (Nigeria) - pricepally.com

Uses the public Meilisearch multi-search endpoint at
meilisearch.pricepally.com directly -- bypasses the Next.js SPA front-end
entirely. The bearer token is a Meilisearch "search-only" key shipped in
every visitor's page load (not a secret credential); no Playwright required.

Prices come back as Medusa.js raw_amount integers in the smallest currency
unit (kobo for NGN) -- divide by 100 to get naira.
"""

import json
import logging

import scrapy

logger = logging.getLogger(__name__)


class PricepallyNgSpider(scrapy.Spider):
    name = "pricepally_ng"
    allowed_domains = ["meilisearch.pricepally.com"]
    currency = "NGN"

    API_URL = "https://meilisearch.pricepally.com/multi-search"
    # Public Meilisearch search-only key, shipped in every visitor's page load.
    SEARCH_KEY = "202d7405c6f6b776bc898a496b12badba4ce86d3a5c5af9b6d2fb37711992ade"
    PAGE_SIZE = 100
    MAX_OFFSET = 2000  # safety cap; catalog is ~1000 products

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 1,
    }

    def _headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.SEARCH_KEY}",
            "Origin": "https://pricepally.com",
            "Referer": "https://pricepally.com/",
        }

    def _request(self, offset):
        payload = {
            "queries": [
                {
                    "indexUid": "products",
                    "q": "",
                    "limit": self.PAGE_SIZE,
                    "offset": offset,
                }
            ]
        }
        return scrapy.Request(
            self.API_URL,
            method="POST",
            headers=self._headers(),
            body=json.dumps(payload),
            callback=self.parse_page,
            meta={"offset": offset},
            dont_filter=True,
        )

    def start_requests(self):
        yield self._request(0)

    def parse_page(self, response):
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error(f"JSON decode failed for {response.url}")
            return

        result = (data.get("results") or [{}])[0]
        hits = result.get("hits") or []
        offset = response.meta["offset"]
        logger.info(f"pricepally_ng: offset={offset} hits={len(hits)}")

        for hit in hits:
            product_id = hit.get("id")
            title = hit.get("title")
            handle = hit.get("handle")
            categories = hit.get("categories") or []
            category = " > ".join(
                c.get("name") for c in categories if c.get("name")
            )
            variants = hit.get("variants") or []
            for variant in variants:
                prices = variant.get("prices") or []
                ngn_price = next(
                    (
                        p
                        for p in prices
                        if (p.get("currency_code") or "").lower() == "ngn"
                    ),
                    None,
                )
                if not ngn_price:
                    continue
                raw = ngn_price.get("raw_amount") or {}
                value = raw.get("value")
                if value is None:
                    continue
                price = float(value) / 100.0  # kobo -> naira
                variant_title = variant.get("title") or ""
                name = f"{title} - {variant_title}".strip(" -")
                url = f"https://pricepally.com/products/{handle}#{variant.get('id')}"

                yield {
                    "product_id": variant.get("id") or product_id,
                    "product_name": name,
                    "price": price,
                    "currency": self.currency,
                    "category": category or None,
                    "url": url,
                    "scraped_at": response.headers.get("Date", b"").decode(
                        "utf-8"
                    ),
                }

        total = result.get("estimatedTotalHits") or 0
        next_offset = offset + self.PAGE_SIZE
        if hits and next_offset < total and next_offset < self.MAX_OFFSET:
            yield self._request(next_offset)
