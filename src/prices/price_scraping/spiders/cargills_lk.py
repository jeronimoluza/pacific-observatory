"""
Spider for Cargills Online (Sri Lanka) -- https://cargillsonline.com/.

The storefront is an AngularJS 1.x SPA and `references/known_blockers.md`
carried it as SKIP ("`{{...}}` placeholder syntax ... `/ProductDetails/<sku>`
URLs never hydrate"). That verdict was written without a network trace: a
Playwright trace on 2026-09-11 found a completely open ASP.NET MVC JSON API
behind the SPA, and the spider below reads it over plain HTTP with no
Playwright at collection time.

Bootstrap chain -- MANDATORY, and the reason a naive probe of the API returns
nothing. A cold POST to the item endpoint returns exactly one synthetic row
`{"ItemName": "No Products Found", "Price": null}`; the catalogue only
materialises once an ASP.NET store session exists:

  1. GET  /                            -> ASP.NET_SessionId
  2. POST /Web/CheckDeliveryOptionV1   (form `PinCode=Colombo`)
     -> ASP.NET_Pincode / ASP.NET_WebStoreType / Asp.Net_WebStoreId (store
        1031, the Colombo dark store). Without this the next call is empty.
  3. POST /Web/GetCategoriesV1         (form, empty body)
     -> 23 top-level categories; `EnId` is the base64 of the numeric
        category id ("MjM=" -> 23 Vegetables, "Nw==" -> 7 Food Cupboard).
  4. POST /Web/GetMenuCategoryItemsPagingV3/  (JSON body, `CategoryId` =
     that `EnId`) -> the whole category in one response when PageSize is
     large; each row carries its own `TotalCount`, which matched the row
     count exactly on every category tested.

Measured live 2026-09-11: 3,967 SKUs across the 23 categories (Health &
Beauty 897, Food Cupboard 428, Snacks & Confectionery 394, Household 359,
Dairy 275, Vegetables 95, Fruits 44, Meats 89, Seafood 24, ...). Sample row:
"Big Onion", SKUCODE VGE0201, Price "205.00" LKR, UOM/UnitSize present.

Prices arrive as display strings with thousands separators ("2,070.00") --
stripped here to a plain decimal. `Mrp` is the pre-discount list price and is
deliberately ignored; `Price` is the shelf price.

Page family read: API (JSON). The API rows carry no PDP slug, so `url` is set
to the SPA's browsable category route rather than a per-product permalink.
"""

import json
import logging
from urllib.parse import quote

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://cargillsonline.com"
_JSON_HEADERS = {
    "Content-Type": "application/json;charset=UTF-8",
    "Accept": "application/json, text/plain, */*",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": _BASE + "/",
}
_FORM_HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Accept": "application/json, text/plain, */*",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": _BASE + "/",
}
# Colombo is the only pincode that resolves to a same-day dark store (1031);
# every other location tested returns DeliveryOption "No" and an empty catalog.
_PINCODE = "Colombo"
# Largest observed category is 897 rows; the endpoint returns the whole
# category in one response, so one generous page beats paginating.
_PAGE_SIZE = 5000


class CargillsLkSpider(scrapy.Spider):
    name = "cargills_lk"
    allowed_domains = ["cargillsonline.com"]
    currency = "LKR"
    language = "en"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS": 1,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1,
        "RETRY_TIMES": 3,
        "USER_AGENT": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(
            _BASE + "/",
            callback=self.parse_home,
            dont_filter=True,
        )

    def parse_home(self, response):
        yield scrapy.Request(
            _BASE + "/Web/CheckDeliveryOptionV1",
            method="POST",
            body="PinCode=" + _PINCODE,
            headers=_FORM_HEADERS,
            callback=self.parse_delivery,
            dont_filter=True,
        )

    def parse_delivery(self, response):
        logger.info("%s: delivery session -> %s", self.name, response.text[:200])
        yield scrapy.Request(
            _BASE + "/Web/GetCategoriesV1",
            method="POST",
            body="",
            headers=_FORM_HEADERS,
            callback=self.parse_categories,
            dont_filter=True,
        )

    def parse_categories(self, response):
        try:
            cats = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("%s: category list did not parse as JSON", self.name)
            return
        logger.info("%s: %d categories", self.name, len(cats))
        for cat in cats:
            en_id = cat.get("EnId")
            if not en_id:
                continue
            body = {
                "CategoryId": en_id,
                "Search": "",
                "Filter": "",
                "PageIndex": 1,
                "PageSize": _PAGE_SIZE,
                "BannerId": "",
                "SectionId": "",
                "CollectionId": "",
                "SectionType": "",
                "DataType": "",
                "SubCatId": "-1",
                "PromoId": "",
            }
            yield scrapy.Request(
                _BASE + "/Web/GetMenuCategoryItemsPagingV3/",
                method="POST",
                body=json.dumps(body),
                headers=_JSON_HEADERS,
                callback=self.parse_items,
                cb_kwargs={"category": cat.get("MenuCategoryName")},
                dont_filter=True,
            )

    def parse_items(self, response, category):
        try:
            items = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("%s: item payload for %s did not parse", self.name, category)
            return
        if not isinstance(items, list):
            return
        # The API signals an empty/unauthorised category with one synthetic row.
        if len(items) == 1 and items[0].get("ItemName") == "No Products Found":
            logger.warning("%s: category %s returned no products", self.name, category)
            return
        logger.info("%s: category %s -> %d items", self.name, category, len(items))
        cat_url = _BASE + "/Product/" + quote(str(category or ""))
        for it in items:
            name = (it.get("ItemName") or "").strip()
            price = self._clean_price(it.get("Price"))
            if not name or price is None:
                continue
            sku = it.get("SKUCODE") or it.get("Id")
            # The SPA exposes no per-product route (the grid opens a modal),
            # so `url` is the browsable category route with a synthetic
            # ?sku= suffix. The suffix exists only to give each row a unique
            # identity -- DuplicationPipeline dedups on url and would
            # otherwise collapse each category to a single row. Query
            # strings are excluded from archive_path_re matching, so this
            # does not affect Common Crawl resolution.
            yield {
                "product_id": sku,
                "product_name": name,
                "price": price,
                "currency": self.currency,
                "category": category,
                "url": f"{cat_url}?sku={quote(str(sku))}" if sku else cat_url,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }

    @staticmethod
    def _clean_price(raw):
        if raw is None:
            return None
        text = str(raw).replace(",", "").strip()
        if not text:
            return None
        try:
            value = float(text)
        except ValueError:
            return None
        if value <= 0:
            return None
        return text
