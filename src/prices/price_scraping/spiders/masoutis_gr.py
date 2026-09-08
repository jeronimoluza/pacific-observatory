"""
Masoutis — https://www.masoutis.gr/ (Northern Greece supermarket chain).

Angular SPA (server shell only, no product markup in raw HTML) backed by
an open JSON API with a lightweight, non-secret auth handshake: GET
`/api/eshop/GetCred` returns a fresh `{Uid, Usl, Key}` triple (no cookie or
login needed), which is echoed back as the `uid`/`usl`/`key` request
headers on every subsequent POST. The POST body also carries a hardcoded,
publicly-visible app key `"PassKey": "Sc@NnSh0p"` (same value for every
client, found via a Playwright network trace of the live site 2026-09-06 —
not a scraped secret, it ships in the client bundle).

Two-step walk:
  1. POST `/api/eshop/GetScanNShopMenuAllLevelsAutoScheduler` -> full
     category menu, ~300 leaf rows (ItemLevel 2) each carrying
     HeaderMenuItem + MenuItemcode. Despite several rows being virtual
     cross-cutting views (Προσφορές/offers, Νέα Προϊόντα/new, Βιολογικά/
     organic, Vegan, Μείωση Τιμής/price-cuts, Προϊόντα Μασούτης/own-brand,
     gluten-free, lactose-free) that overlap the base grocery categories,
     every (header, subitem) pair is still queried -- duplicate items
     across these views share the same Itemcode/url and are deduped by
     DuplicationPipeline downstream.
  2. POST `/api/eshop/GetPromoItemWithListCouponsSubCategoriesAutoPromosv2`
     with `Itemcode: "<HeaderMenuItem>,<MenuItemcode>"` -> up to 50 items
     for that leaf. The endpoint name says "Promo"/"Coupons" but it is the
     general item-listing endpoint for the whole catalogue, not an
     offers-only feed -- verified live: querying Κρεοπωλείο/Κοτόπουλα
     (Butchery/Chicken) returns 50 regular-priced items with
     StartPrice == PosPrice (no discount), not just promotional ones.
     No working pagination parameter was found (`"Page": "2"` is silently
     ignored) -- categories cap at 50 items/leaf, same accepted limitation
     as the Wolt-venue spiders in this repo.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.masoutis.gr"
_PASSKEY = "Sc@NnSh0p"
_JSON_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
}


class MasoutisGrSpider(scrapy.Spider):
    name = "masoutis_gr"
    allowed_domains = ["masoutis.gr"]
    currency = "EUR"
    language = "el"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            f"{BASE_URL}/api/eshop/GetCred",
            callback=self.parse_cred,
            errback=self.errback,
        )

    def parse_cred(self, response):
        cred = json.loads(response.text)
        auth_headers = {
            **_JSON_HEADERS,
            "uid": cred["Uid"],
            "usl": cred["Usl"],
            "key": cred["Key"],
        }
        yield scrapy.Request(
            f"{BASE_URL}/api/eshop/GetScanNShopMenuAllLevelsAutoScheduler",
            method="POST",
            headers=auth_headers,
            body=json.dumps({"PassKey": _PASSKEY}),
            callback=self.parse_menu,
            meta={"auth_headers": auth_headers},
            errback=self.errback,
        )

    def parse_menu(self, response):
        auth_headers = response.meta["auth_headers"]
        rows = json.loads(response.text)
        seen = set()
        for row in rows:
            header = row.get("HeaderMenuItem")
            sub = row.get("MenuItemcode")
            if header is None or sub is None:
                continue
            key = (header, sub)
            if key in seen:
                continue
            seen.add(key)
            category_name = row.get("MenuItemDescr") or row.get("HeaderMenuItemDescr") or ""
            body = {
                "PassKey": _PASSKEY,
                "Itemcode": f"{header},{sub}",
                "ItemDescr": "0",
                "IfWeight": "1",
                "ServiceResponse": "",
                "Token": "",
                "Zip": "",
                "BrandName": "",
                "TeamId": "",
                "ExtraFilter": "",
            }
            yield scrapy.Request(
                f"{BASE_URL}/api/eshop/GetPromoItemWithListCouponsSubCategoriesAutoPromosv2",
                method="POST",
                headers=auth_headers,
                body=json.dumps(body),
                callback=self.parse_items,
                meta={"category_name": category_name},
                errback=self.errback,
            )
        logger.info(f"{self.name}: leaf categories found={len(seen)}")

    def parse_items(self, response):
        category_name = response.meta["category_name"]
        try:
            items = json.loads(response.text)
        except ValueError:
            logger.warning(f"{self.name}: bad JSON at {response.url}")
            return
        if not isinstance(items, list):
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        found = 0
        for it in items:
            product_id = it.get("Itemcode")
            name = it.get("ItemDescr")
            price = it.get("PosPrice")
            if not product_id or not name or price is None:
                continue
            try:
                price_val = float(price)
            except (TypeError, ValueError):
                continue
            if price_val == 0:
                continue

            found += 1
            yield {
                "product_id": str(product_id),
                "product_name": str(name).strip()[:500],
                "category": category_name,
                "price": str(price_val),
                "currency": self.currency,
                "available": True,
                "url": it.get("ItemDescrLink") or f"{BASE_URL}/categories/item/?{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        logger.info(f"{self.name}: {response.url} items={len(items)} yielded={found}")

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
