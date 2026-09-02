"""
BSSD Alimentation (Benin) — https://bssdalimentation.vercel.app/.

Single-page React app (Vercel-hosted) with no server-rendered products and
no conventional platform API. The catalog lives entirely in a public
Firestore database (project "bssd-alimentation", collection "produits")
that the client reads directly with the Firebase SDK and NO auth — writes
are gated to one admin account by Firestore security rules, but reads are
public. The same data is reachable over plain HTTPS via the Firestore REST
API, so this needs no JS bundle to be executed:

    GET https://firestore.googleapis.com/v1/projects/bssd-alimentation/
        databases/(default)/documents/produits?pageSize=300&pageToken=<tok>

Each document has nom/promo/barre/cat fields (promo = current selling
price, barre = struck-through reference price, both plain FCFA integers,
no minor-unit division needed). Pagination follows the response's own
nextPageToken cursor, never a synthesised offset.

Probed live 2026-08-31: 25 live documents, all real distinct FCFA prices
(400-32000), covering rice/oil/pack combos plus individual staples
(spaghetti, sardines, milk, sugar, coffee, tomato paste). Site copy is
explicit about Cotonou/Calavi delivery and Mobile Money payment (Benin).

The SPA has one URL for every product (client-side routing only), so each
row is given a unique url fragment keyed on the Firestore doc id —
otherwise DuplicationPipeline's url-based dedup would keep only the first
row.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://bssdalimentation.vercel.app/"
API_URL = (
    "https://firestore.googleapis.com/v1/projects/bssd-alimentation/"
    "databases/(default)/documents/produits"
)
PAGE_SIZE = 300


class BssdBjSpider(scrapy.Spider):
    name = "bssd_bj"
    allowed_domains = ["firestore.googleapis.com"]
    currency = "XOF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def _page_url(self, page_token: str | None) -> str:
        url = f"{API_URL}?pageSize={PAGE_SIZE}"
        if page_token:
            url += f"&pageToken={page_token}"
        return url

    async def start(self):
        yield scrapy.Request(self._page_url(None), callback=self.parse_page)

    def parse_page(self, response):
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON response at {response.url}")
            return

        docs = data.get("documents") or []
        logger.info(f"{self.name}: got {len(docs)} docs")
        for doc in docs:
            item = self._item(doc)
            if item:
                yield item

        next_token = data.get("nextPageToken")
        if next_token:
            yield scrapy.Request(self._page_url(next_token), callback=self.parse_page)

    @staticmethod
    def _field(fields: dict, key: str):
        val = fields.get(key)
        if not isinstance(val, dict):
            return None
        for kind in ("stringValue", "integerValue", "doubleValue"):
            if kind in val:
                return val[kind]
        return None

    def _item(self, doc: dict):
        doc_id = (doc.get("name") or "").rsplit("/", 1)[-1]
        fields = doc.get("fields") or {}
        name = self._field(fields, "nom")
        price = self._field(fields, "promo")
        if not doc_id or not name or price is None:
            return None
        try:
            price_val = float(price)
        except (TypeError, ValueError):
            return None
        if price_val <= 0:
            # "prix à préciser" placeholder rows carry no real price.
            return None
        return {
            "product_id": doc_id,
            "product_name": str(name).strip()[:500],
            "category": self._field(fields, "cat"),
            "price": str(price_val),
            "currency": self.currency,
            "available": True,
            "url": f"{BASE_URL}#produit-{doc_id}",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
