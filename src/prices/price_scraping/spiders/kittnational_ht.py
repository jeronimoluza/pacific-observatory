"""
KittNational (Haiti) — https://kittnational.com/.

React SPA (Vite build) with no server-rendered product HTML and no
conventional REST API of its own. The catalogue lives entirely in a
public Supabase Postgres instance, reached through a "helloreaddy.com"
function-URL proxy in front of the real Supabase project (project ref
2kug72le92fjtj5suphu), via standard PostgREST:
GET /rest/v1/product_items?select=...&limit=&offset=.

Auth key: the bundle (/assets/index-D4P3LgCh.js, fetched 2026-09-10)
embeds `sb_publishable_aI5EmGRPfPO04glpzr6TmlDrvcFSjPcY` -- Supabase's
newer "publishable key" format (the direct successor to the legacy JWT
anon key), used client-side for anonymous reads. This is NOT a
service_role/secret key -- no `sb_secret_` or `service_role` string
appears anywhere in the bundle -- so using it here is the intended
public-read pattern (see trinicart_tt.py for the equivalent legacy-JWT
version of the same pattern).

Enumerability verified live 2026-09-10: `Prefer: count=exact` on
`product_items?status=eq.active` reports 1,673 active rows (1,676 total,
3 inactive); `?limit=100&offset=0` vs `?limit=100&offset=100` (both
`order=id`) returned zero id overlap between the two pages. This is a
real general marketplace catalogue, not a widget query -- confirmed by
a separate `product_categories` table (34 rows: Elektronik, Rad & Soulye,
Kay & Kizin, ...) that `product_items.category_id` foreign-keys into.
(`menu_categories`, a UUID-keyed table for an unrelated food/menu
feature, is NOT the product category table -- do not confuse the two.)

Currency: every sampled row carries `currency: "HTG"` directly on the
row (Haitian Gourde) -- correct geography, no USD-quoting anomaly.
Sample real rows: "Nutella — Bokal Pate Chokola 26.5 oz" HTG 1427.15;
"Ponp Lwil Toyota Corolla 4A-FE 1.6L — Aisin OPT-012" HTG 6900.00
(HTG 5865.00 after its active discount).

PDP URL pattern confirmed live: /market/product/<id> (found in the Vite
bundle's route table as `path:\`/market/product/:id\``, HTTP 200 verified
for a real id).
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://2kug72le92fjtj5suphu.helloreaddy.com/rest/v1/product_items"
SUPABASE_KEY = "sb_publishable_aI5EmGRPfPO04glpzr6TmlDrvcFSjPcY"
PAGE_SIZE = 500
MAX_PAGES = 20  # safety cap; catalogue measured at 1,676 rows (~4 pages)

_CATEGORIES_URL = (
    "https://2kug72le92fjtj5suphu.helloreaddy.com/rest/v1/product_categories"
    "?select=id,name"
)


class KittnationalHtSpider(scrapy.Spider):
    name = "kittnational_ht"
    allowed_domains = ["helloreaddy.com"]
    currency = "HTG"
    language = "ht"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
    }

    def _headers(self):
        return {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Accept": "application/json",
        }

    async def start(self):
        yield scrapy.Request(
            _CATEGORIES_URL,
            headers=self._headers(),
            callback=self.parse_categories,
        )

    def parse_categories(self, response):
        cat_map = {}
        try:
            for row in json.loads(response.text):
                cat_map[row["id"]] = row.get("name")
        except (json.JSONDecodeError, KeyError, TypeError):
            logger.warning(f"{self.name}: could not parse categories; names will be null")
        yield self._page_request(0, cat_map)

    def _page_request(self, offset: int, cat_map: dict):
        url = (
            f"{BASE_URL}?select=id,name,category_id,status,currency,price,"
            f"discount_enabled,discount_price&status=eq.active&order=id"
            f"&limit={PAGE_SIZE}&offset={offset}"
        )
        return scrapy.Request(
            url,
            headers=self._headers(),
            callback=self.parse_page,
            meta={"offset": offset, "cat_map": cat_map},
        )

    def parse_page(self, response):
        offset = response.meta["offset"]
        cat_map = response.meta["cat_map"]
        try:
            rows = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error(f"{self.name}: JSON decode failed at offset={offset}")
            return
        if not isinstance(rows, list):
            logger.error(f"{self.name}: unexpected payload shape at offset={offset}")
            return

        logger.info(f"{self.name}: offset={offset} rows={len(rows)}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for row in rows:
            item = self._item(row, cat_map, scraped_at)
            if item:
                yield item

        if len(rows) >= PAGE_SIZE and (offset // PAGE_SIZE + 1) < MAX_PAGES:
            yield self._page_request(offset + PAGE_SIZE, cat_map)

    def _item(self, row: dict, cat_map: dict, scraped_at: str):
        price = row.get("price")
        if row.get("discount_enabled") and row.get("discount_price") is not None:
            price = row["discount_price"]
        try:
            price = float(price)
        except (TypeError, ValueError):
            return None
        if price <= 0:
            return None
        name = (row.get("name") or "").strip()
        if not name:
            return None
        return {
            "product_id": str(row.get("id")),
            "product_name": name[:500],
            "category": cat_map.get(row.get("category_id")),
            "price": str(price),
            "currency": row.get("currency") or self.currency,
            "available": True,
            "url": f"https://kittnational.com/market/product/{row.get('id')}",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
