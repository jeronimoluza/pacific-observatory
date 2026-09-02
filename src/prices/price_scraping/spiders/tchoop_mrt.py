"""
Tchoop (Mauritania) — https://www.tchoopapp.com/.

Firebase/React SPA (food + grocery delivery, Nouakchott). The marketing
site is a static shell with no server-rendered catalog and no conventional
platform API, but the app reads its data straight from a public Firestore
database (project "tchoop-15725") with the Firebase web SDK. Firestore
security rules make the top-level "restaurants" and "menuItems"
collections publicly LISTABLE over plain HTTPS, so this needs no JS bundle
execution — most other collection names probed (products, stores, shops,
markets, items, menus, dishes, ...) return 403 PERMISSION_DENIED, but
these two do not:

    GET https://firestore.googleapis.com/v1/projects/tchoop-15725/
        databases/(default)/documents/restaurants?pageSize=300

"restaurants" is 100% food/dining businesses (32 live entries probed
2026-08-31) EXCEPT one grocery vertical, "Prime Mart" (categories:
Épicerie, Fruits & Légumes, Lait & Crème, Fromages, Charcuterie, Beurre &
Œufs, Poissons et fruits de mer, ...) — this is the only real supermarket
in the marketplace today. The spider scopes to grocery businesses only, by
requiring "épicerie" to appear (case/accent-insensitive) among a
restaurant's declared menu categories; restaurant food vendors do not use
that word. This is future-proof if Tchoop onboards more grocery stores
later, without hardcoding an id.

Per-store products live in the top-level "menuItems" collection, keyed by
restaurantId — filtered server-side with a Firestore structured query
(:runQuery), not the general 403'd "products" collection:

    POST .../documents:runQuery
    {"structuredQuery": {"from": [{"collectionId": "menuItems"}],
      "where": {"fieldFilter": {"field": {"fieldPath": "restaurantId"},
        "op": "EQUAL", "value": {"stringValue": "<restaurant doc id>"}}},
      "limit": 1000}}

Probed live 2026-08-31: Prime Mart carries 163 menuItems, 137 with a
non-zero price (26 are unpriced/unavailable placeholder rows, skipped) —
real MRU grocery SKUs (packaged food, dairy, condiments, produce), e.g.
"Nestlé Nature Ferments Lactiques - 6x100g" 180 MRU, "Aïoli Choví Style
Artisanal à l'Huile d'Olive (150ml)" 240 MRU. currenciesAccepted in the
site's own JSON-LD is MRU; the app was founded in 2024 (JSON-LD
foundingDate), well after the 2018 MRO->MRU redenomination, so these are
new-ouguiya figures, not the 10x-larger old MRO.

The marketing site has no server-rendered per-product page (every route,
incl. /restaurants/<slug>, serves the same SPA shell), so each row is
given a synthetic url keyed on the Firestore menuItem doc id to avoid
DuplicationPipeline's url-based dedup collapsing distinct products.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.tchoopapp.com/"
PROJECT_URL = (
    "https://firestore.googleapis.com/v1/projects/tchoop-15725/"
    "databases/(default)/documents"
)
GROCERY_KEYWORD = "picerie"  # matches "Épicerie"/"épicerie", accent-insensitive


class TchoopMrtSpider(scrapy.Spider):
    name = "tchoop_mrt"
    allowed_domains = ["firestore.googleapis.com"]
    currency = "MRU"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            f"{PROJECT_URL}/restaurants?pageSize=300", callback=self.parse_restaurants
        )

    @staticmethod
    def _decode(value: dict):
        if "stringValue" in value:
            return value["stringValue"]
        if "integerValue" in value:
            return int(value["integerValue"])
        if "doubleValue" in value:
            return value["doubleValue"]
        if "booleanValue" in value:
            return value["booleanValue"]
        if "mapValue" in value:
            return {
                k: TchoopMrtSpider._decode(v)
                for k, v in (value["mapValue"].get("fields") or {}).items()
            }
        if "arrayValue" in value:
            return [
                TchoopMrtSpider._decode(v)
                for v in (value["arrayValue"].get("values") or [])
            ]
        return None

    def _fields(self, doc: dict) -> dict:
        return {k: self._decode(v) for k, v in (doc.get("fields") or {}).items()}

    def parse_restaurants(self, response):
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON restaurants response")
            return

        docs = data.get("documents") or []
        logger.info(f"{self.name}: {len(docs)} restaurants total")

        grocers = []
        for doc in docs:
            fields = self._fields(doc)
            categories = fields.get("categories") or []
            is_grocer = any(GROCERY_KEYWORD in str(c).lower() for c in categories)
            if is_grocer:
                doc_id = (doc.get("name") or "").rsplit("/", 1)[-1]
                grocers.append((doc_id, fields.get("name") or doc_id))

        logger.info(f"{self.name}: grocery stores matched={grocers}")
        for store_id, store_name in grocers:
            body = {
                "structuredQuery": {
                    "from": [{"collectionId": "menuItems"}],
                    "where": {
                        "fieldFilter": {
                            "field": {"fieldPath": "restaurantId"},
                            "op": "EQUAL",
                            "value": {"stringValue": store_id},
                        }
                    },
                    "limit": 1000,
                }
            }
            yield scrapy.Request(
                f"{PROJECT_URL}:runQuery",
                method="POST",
                body=json.dumps(body),
                headers={"Content-Type": "application/json"},
                callback=self.parse_menu_items,
                meta={"store_id": store_id, "store_name": store_name},
            )

    def parse_menu_items(self, response):
        store_id = response.meta["store_id"]
        store_name = response.meta["store_name"]
        try:
            results = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON menuItems response for {store_id}")
            return

        count = 0
        for entry in results:
            doc = entry.get("document")
            if not doc:
                continue
            item = self._item(doc, store_name)
            if item:
                count += 1
                yield item

        logger.info(
            f"{self.name}: store={store_name} ({store_id}) raw={len(results)} priced={count}"
        )
        if len(results) >= 1000:
            logger.warning(
                f"{self.name}: store={store_name} hit the 1000-row query limit; "
                "results may be truncated (no cursor implemented)"
            )

    def _item(self, doc: dict, store_name: str):
        fields = self._fields(doc)
        if fields.get("isAvailable") is False:
            return None

        price = fields.get("price")
        try:
            price_val = float(price)
        except (TypeError, ValueError):
            return None
        if price_val <= 0:
            return None

        name_map = fields.get("name") or {}
        name = name_map.get("fr") or name_map.get("en") or name_map.get("ar")
        if not name:
            return None

        doc_id = (doc.get("name") or "").rsplit("/", 1)[-1]
        category = fields.get("category") or store_name

        return {
            "product_id": doc_id,
            "product_name": str(name).strip()[:500],
            "category": category,
            "price": str(price_val),
            "currency": self.currency,
            "available": True,
            "url": f"{BASE_URL}?store={store_name}&item={doc_id}",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
