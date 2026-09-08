"""
Spider for Konga (Nigeria) - konga.com

Konga's category pages ship a client-rendered skeleton (Next.js) -- the raw
HTML carries only price-filter facet labels, not real product cards. Recovered
via Playwright network trace: the front-end calls a hosted search service at
kss.igbimo.com/search with a "kss_pub_..." API key that is shipped in every
visitor's page load (a public search key, not a secret). No Playwright
required to scrape -- plain HTTP POST with that key.

Konga is a marketplace (first-party "Konga Retail" + third-party sellers
mixed in one catalog, distinguished by `konga_fulfilment_type`) -- tagged
channel: marketplace accordingly.
"""

import logging

import scrapy
from scrapy.http import JsonRequest

logger = logging.getLogger(__name__)


class KongaNgSpider(scrapy.Spider):
    name = "konga_ng"
    allowed_domains = ["kss.igbimo.com"]
    currency = "NGN"

    API_URL = "https://kss.igbimo.com/search"
    API_KEY = "kss_pub_BlDPgUB4XUJwJgh7oyliGBFASQLAXR1i4"
    HIT_PER_PAGE = 50
    MAX_PAGE = 40  # safety cap

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 1,
    }

    def _headers(self):
        return {
            "Content-Type": "application/json",
            "Referer": "https://www.konga.com/",
            "kss-api-key": self.API_KEY,
        }

    def _request(self, page):
        payload = {
            "name": "catalog_store_konga_ranking",
            "q": "*",
            "page": page,
            "hitPerPage": self.HIT_PER_PAGE,
            "facet_by": "",
        }
        return JsonRequest(
            self.API_URL,
            method="POST",
            headers=self._headers(),
            data=payload,
            callback=self.parse_page,
            meta={"page": page},
            dont_filter=True,
        )

    def start_requests(self):
        yield self._request(1)

    def parse_page(self, response):
        try:
            data = response.json()
        except ValueError:
            logger.error(f"JSON decode failed for {response.url}")
            return

        hits = (data.get("data") or {}).get("hits") or []
        page = response.meta["page"]
        logger.info(f"konga_ng: page={page} hits={len(hits)}")

        for hit in hits:
            product_id = hit.get("objectid") or hit.get("sku")
            name = hit.get("name")
            # special_price wins when active; falls back to the list price.
            price = hit.get("special_price") or hit.get("price")
            if not name or not product_id or price is None:
                continue
            url_key = hit.get("url_key")
            url = (
                f"https://www.konga.com/product/{url_key}"
                if url_key
                else f"https://www.konga.com/product/{product_id}"
            )
            yield {
                "product_id": product_id,
                "product_name": name,
                "price": price,
                "currency": self.currency,
                "category": hit.get("brand"),
                "url": url,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }

        if hits and page < self.MAX_PAGE:
            yield self._request(page + 1)
