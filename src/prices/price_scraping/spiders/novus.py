"""
Spider for NOVUS (Ukraine) - novus.ua / novus.zakaz.ua

Uses the public zakaz.ua storefront JSON API directly (Tier 1B) — bypasses the
SPA front-end, no Playwright. NOVUS is a major Kyiv-region supermarket chain;
its catalogue spans the full grocery basket, so COICOP is left to the
downstream Gemini classifier (deferred_gemini).

Key gotcha: the API returns `price` in KOPECKS (integer) — divide by 100 to get
UAH. e.g. 6629 -> 66.29 UAH.
"""

import json
import logging

import scrapy

logger = logging.getLogger(__name__)


class NovusSpider(scrapy.Spider):
    name = "novus"
    allowed_domains = ["stores-api.zakaz.ua"]
    currency = "UAH"

    STORE_ID = "482010105"  # NOVUS SkyMall (a full-range store)
    PAGES_PER_CATEGORY = 2
    _API = "https://stores-api.zakaz.ua/stores/{sid}/categories/{cid}/products/?page={page}"
    _CATS_API = "https://stores-api.zakaz.ua/stores/{sid}/categories/"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 1,
    }

    @property
    def _headers(self):
        return {
            "Accept": "application/json",
            "Accept-Language": "uk",
            "x-chain": "novus",
        }

    def start_requests(self):
        yield scrapy.Request(
            self._CATS_API.format(sid=self.STORE_ID),
            headers=self._headers,
            callback=self.parse_categories,
        )

    def parse_categories(self, response):
        try:
            cats = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("novus: category JSON decode failed for %s", response.url)
            return
        logger.info("novus: %d categories", len(cats))
        for cat in cats:
            cid = cat.get("id")
            title = (cat.get("title") or "").strip()
            if not cid:
                continue
            for page in range(1, self.PAGES_PER_CATEGORY + 1):
                yield scrapy.Request(
                    self._API.format(sid=self.STORE_ID, cid=cid, page=page),
                    headers=self._headers,
                    callback=self.parse_products,
                    meta={"category": title},
                )

    def parse_products(self, response):
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("novus: product JSON decode failed for %s", response.url)
            return
        items = payload.get("results") or []
        category = response.meta.get("category")
        logger.info("novus: %s -> %d items", response.url, len(items))
        for it in items:
            price_kop = it.get("price")
            if price_kop is None:
                continue
            try:
                price = f"{int(price_kop) / 100:.2f}"
            except (TypeError, ValueError):
                continue
            name = (it.get("title") or "").strip()
            if not name:
                continue
            yield {
                "product_id": it.get("ean") or it.get("sku"),
                "product_name": name,
                "price": price,
                "currency": (it.get("currency") or self.currency).upper(),
                "category": category,
                "url": it.get("web_url"),
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
