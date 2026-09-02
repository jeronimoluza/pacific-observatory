"""
Pharmacie du Port (Benin) — https://phcieduport.com/.

Static HTML site (no server-rendered product listing, no WooCommerce/
Shopify/etc). /wp-json/... is not present. The homepage's own JS bundle
(js/supabaseClient.js, js/products.js) hardcodes a public Supabase project
and reads the catalog client-side with the anon key — no auth needed to
read:

    project:  https://ampktfwcpopkomrsckjm.supabase.co
    schema:   pharmacie_port   (non-default; must be set via the
              Accept-Profile request header, not a query param)
    table:    products

    GET {project}/rest/v1/products?select=*&order=id&limit=1000&offset=<n>
    Headers: apikey: <anon key>, Accept-Profile: pharmacie_port

Paginated 1000 rows/request by offset; PostgREST returns fewer than 1000
rows on the final page, which is the stop condition (matches the site's
own products.js walk, which loops the same way). Probed live 2026-08-31:
4319 total distinct pharmaceutical SKUs, real distinct FCFA prices (e.g.
'ABZOLE 400MG CP B/100' = 11675 XOF), all integers (no minor-unit
division). Site is explicitly Cotonou/Benin (title, order.html copy
"Retrait rapide à Cotonou"), FCFA throughout.

The catalog has no per-product detail URL (search-modal only, no routed
product page), so each row gets a unique url fragment keyed on the
Supabase row id to avoid DuplicationPipeline's url-based dedup collapsing
every row from this single API endpoint down to one.

The anon key is a Supabase PUBLISHABLE key (prefix sb_publishable_),
scoped by Supabase's row-level security to whatever the project owner
exposed — the same key the site's own front end ships in plain JS. This
is a Tier 1B read, not a credential lift.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://phcieduport.com/"
API_URL = "https://ampktfwcpopkomrsckjm.supabase.co/rest/v1/products"
ANON_KEY = "sb_publishable_FMDalRvzL6h5zW_4fTXt5g_I4dvctkD"
PAGE_SIZE = 1000


class PhcieduportBjSpider(scrapy.Spider):
    name = "phcieduport_bj"
    allowed_domains = ["ampktfwcpopkomrsckjm.supabase.co"]
    currency = "XOF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def _page_url(self, offset: int) -> str:
        return f"{API_URL}?select=*&order=id&limit={PAGE_SIZE}&offset={offset}"

    def _headers(self) -> dict:
        return {
            "apikey": ANON_KEY,
            "Authorization": f"Bearer {ANON_KEY}",
            "Accept-Profile": "pharmacie_port",
        }

    async def start(self):
        yield scrapy.Request(
            self._page_url(0),
            headers=self._headers(),
            callback=self.parse_page,
            meta={"offset": 0},
        )

    def parse_page(self, response):
        try:
            rows = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON response at {response.url}")
            return
        if not isinstance(rows, list):
            logger.warning(f"{self.name}: unexpected payload shape at {response.url}")
            return

        offset = response.meta["offset"]
        logger.info(f"{self.name}: offset={offset} got={len(rows)}")
        for row in rows:
            item = self._item(row)
            if item:
                yield item

        if len(rows) >= PAGE_SIZE:
            next_offset = offset + PAGE_SIZE
            yield scrapy.Request(
                self._page_url(next_offset),
                headers=self._headers(),
                callback=self.parse_page,
                meta={"offset": next_offset},
            )

    def _item(self, row: dict):
        row_id = row.get("id")
        name = row.get("name")
        price = row.get("price")
        if row_id is None or not name or price is None:
            return None
        try:
            price_val = float(price)
        except (TypeError, ValueError):
            return None
        if price_val <= 0:
            return None
        return {
            "product_id": str(row_id),
            "product_name": str(name).strip()[:500],
            "category": row.get("category"),
            "price": str(price_val),
            "currency": self.currency,
            "available": bool(row.get("in_stock", True)),
            "url": f"{BASE_URL}#produit-{row_id}",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
