"""
Shared base for Ukraine supermarket spiders on the zakaz.ua storefront platform.

Several major UA grocery chains (NOVUS, Auchan, METRO, Tavria-V, ...) expose a
public JSON storefront API at https://stores-api.zakaz.ua/. The API works from
non-UA IPs even when the retailers' own SPA domains geo-block, and every chain
shares the exact same request/response shape — only the `x-chain` header and a
store id differ. So the per-chain spiders are one-liners over this base.

Tier 1B (JSON API), no Playwright. The catalogue spans the full grocery basket,
so COICOP is left to the downstream Gemini classifier (deferred_gemini).

Key gotcha: the API returns `price` in KOPECKS (integer) — divide by 100 to get
UAH. e.g. 6629 -> 66.29 UAH.

To add a chain: subclass, set `name`, `chain`, `STORE_ID`. Find a valid store id
with:
    curl -H 'x-chain: <chain>' -H 'Accept-Language: uk' \
        https://stores-api.zakaz.ua/stores/
"""

import json
import logging

import scrapy

logger = logging.getLogger(__name__)


class ZakazBaseSpider(scrapy.Spider):
    # Subclasses MUST override these three.
    name = None
    chain = None
    STORE_ID = None

    currency = "UAH"
    allowed_domains = ["stores-api.zakaz.ua"]

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
            "x-chain": self.chain,
        }

    def start_requests(self):
        if not (self.name and self.chain and self.STORE_ID):
            raise scrapy.exceptions.CloseSpider(
                "ZakazBaseSpider subclass must set name, chain and STORE_ID"
            )
        yield scrapy.Request(
            self._CATS_API.format(sid=self.STORE_ID),
            headers=self._headers,
            callback=self.parse_categories,
        )

    def parse_categories(self, response):
        try:
            cats = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("%s: category JSON decode failed for %s", self.name, response.url)
            return
        logger.info("%s: %d categories", self.name, len(cats))
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
            logger.error("%s: product JSON decode failed for %s", self.name, response.url)
            return
        items = payload.get("results") or []
        category = response.meta.get("category")
        logger.info("%s: %s -> %d items", self.name, response.url, len(items))
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
