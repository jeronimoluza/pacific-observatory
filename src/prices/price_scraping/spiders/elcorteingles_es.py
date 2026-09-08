"""
Spider for El Corte Inglés Supermercado (Spain) — https://www.elcorteingles.es/supermercado/.

Server-rendered "Moonshine" storefront: every category listing page embeds
`window.__MOONSHINE_STATE__ = {...}` with the live product grid at
`viewData.plp.products` (24 entries/page). The array is MIXED -- some
entries are ad/sponsor slots (no `priceSpecification` key), others are
real products (`id`, `description`, `priceSpecification.price`,
`priceSpecification.salePrice`, category chain) -- filter on
`priceSpecification` presence.

Pagination is a plain `/supermercado/<slug>/<n>/` path segment; the state
blob's own `viewData.plp.pagination.path_next` gives the next page's path
directly, and `totalPages` gives the walk bound (verified live:
`frescos` reports totalPages=107 at 24/page = ~2,558 products). No WAF
encountered (curl_cffi chrome124, 200 throughout, 1.8MB category page).

`priceSpecification.salePrice` is populated (and lower than `.price`)
whenever `has_discount` is true -- this looks like the EU Price
Indication Directive Article 6a-relevant field the shard's AI_NOTES
flagged, but it was NOT verified live to be a genuine 30-day-low
(vs. just "current promo price"), so this spider emits salePrice-or-price
as the single current shelf price rather than asserting the Article 6a
semantics.

`coicop_classification: classifier` / `coicop_codes: null` -- general
supermarket spanning many divisions, same convention as carrefour_pl /
carrefour_es.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.elcorteingles.es"
_TOP_CATEGORIES = [
    "alimentacion-general",
    "bebes",
    "bebidas",
    "congelados",
    "cuidado-personal-y-belleza",
    "desayunos-dulces-y-pan",
    "drogueria-y-limpieza",
    "frescos",
    "lacteos",
    "mascotas",
    "nutricion-y-bienestar",
]
_STATE_MARKER = "__MOONSHINE_STATE__"
MAX_PAGES_PER_CATEGORY = 120  # safety cap, above the ~107-page observed max


def _parse_state(text):
    idx = text.find(_STATE_MARKER)
    if idx == -1:
        return None
    start = text.find("{", idx)
    if start == -1:
        return None
    try:
        data, _end = json.JSONDecoder().raw_decode(text, start)
    except (ValueError, TypeError):
        return None
    return data


class ElcorteinglesEsSpider(scrapy.Spider):
    name = "elcorteingles_es"
    allowed_domains = ["elcorteingles.es"]
    currency = "EUR"
    language = "es"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "DOWNLOAD_TIMEOUT": 30,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        for slug in _TOP_CATEGORIES:
            yield scrapy.Request(
                f"{_BASE}/supermercado/{slug}/1/",
                callback=self.parse_category,
                meta={"slug": slug, "page": 1},
            )

    def parse_category(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]

        data = _parse_state(response.text)
        if data is None:
            logger.warning("elcorteingles_es: no __MOONSHINE_STATE__ on %s", response.url)
            return

        try:
            plp = data["viewData"]["plp"]
            products = plp["products"] or []
            pagination = plp["pagination"] or {}
        except (KeyError, TypeError):
            logger.warning("elcorteingles_es: unexpected shape on %s", response.url)
            return

        total_pages = pagination.get("totalPages") or 1
        real = [p for p in products if isinstance(p, dict) and "priceSpecification" in p]
        logger.info(
            "elcorteingles_es: %s page=%d -> %d/%d real products (totalPages=%s)",
            slug,
            page,
            len(real),
            len(products),
            total_pages,
        )

        for entry in real:
            item = self._item(entry, slug)
            if item:
                yield item

        next_path = pagination.get("path_next")
        if real and page < total_pages and page < MAX_PAGES_PER_CATEGORY and next_path:
            yield scrapy.Request(
                f"{_BASE}{next_path}",
                callback=self.parse_category,
                meta={"slug": slug, "page": page + 1},
            )

    def _item(self, entry, slug):
        name = entry.get("description")
        spec = entry.get("priceSpecification") or {}
        price = spec.get("salePrice") or spec.get("price")
        if not name or not price:
            return None

        categories = entry.get("categories") or []
        category = None
        for c in categories:
            if c.get("name"):
                category = c["name"]
                break

        product_id = entry.get("id") or entry.get("id_atg")
        rel_url = entry.get("url")
        url = f"{_BASE}{rel_url}" if rel_url else None

        return {
            "product_id": product_id or url or name,
            "product_name": str(name).strip()[:500],
            "category": category or slug,
            "price": str(price).replace(",", "."),
            "currency": self.currency,
            "available": True,
            "url": url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
