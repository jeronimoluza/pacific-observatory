"""
Spider for Carrefour Spain (Online Supermarket) — https://www.carrefour.es/supermercado.

Custom Node/Express storefront (NOT Next.js like carrefour_pl): every page
embeds a `window.__INITIAL_STATE__ = {...}` JSON blob. Category listing
pages carry the live product grid at
`productCardList.results.items` (24 items/page), with the total count at
`productCardList.results.pagination.total_results`. Pagination is a plain
`?offset=N` query param on the SAME category URL — verified live that
`?page=2` is a no-op (returns offset 0 again) but `?offset=24` returns a
disjoint set of items.

No WAF on category/listing pages (plain curl_cffi chrome124, 200
throughout). `leroymerlin.es`'s Akamai challenge and `amazon.es`'s bot-JS
shell do NOT apply here — this is a different Carrefour Spain-only stack,
unrelated to the Majid Al Futtaim Gulf-Carrefour Akamai tenant documented
elsewhere in known_blockers.md.

Each item carries `product_id`, `name`, `price` (formatted "N,NN €"),
`price_per_unit`, `measure_unit`, `catalog` (food/non-food-ish tag) and a
relative `url`. `coicop_classification: classifier` in the YAML — no
hardcoded COICOP code here, this is a general supermarket spanning many
divisions, left to the downstream classifier like carrefour_pl.

Walk strategy: the ~9 top-level category slugs from the homepage nav
(`/supermercado/<slug>/<catid>/c`), each paginated via `?offset=N` in
steps of 24 until `total_results` is reached or a page returns 0 items.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.carrefour.es"
_TOP_CATEGORIES = [
    ("bebe", "cat20006"),
    ("bebidas", "cat20003"),
    ("congelados", "cat21449123"),
    ("cuidado-personal-e-higiene", "cat20004"),
    ("drogueria-y-limpieza", "cat20005"),
    ("frescos", "cat20002"),
    ("la-despensa", "cat20001"),
    ("mascotas", "cat20007"),
    ("parafarmacia", "cat20008"),
]
_PAGE_SIZE = 24
_INITIAL_STATE_MARKER = "__INITIAL_STATE__"
_PRICE_RE = re.compile(r"([\d.,]+)")
MAX_OFFSET_PER_CATEGORY = 2400  # safety cap (100 pages @ 24/page)


def _parse_initial_state(text):
    idx = text.find(_INITIAL_STATE_MARKER)
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


def _parse_price(raw):
    if not raw:
        return None
    m = _PRICE_RE.search(str(raw).replace(".", "").replace(",", "."))
    return m.group(1) if m else None


class CarrefourEsSpider(scrapy.Spider):
    name = "carrefour_es"
    allowed_domains = ["carrefour.es"]
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
        for slug, cat_id in _TOP_CATEGORIES:
            yield scrapy.Request(
                f"{_BASE}/supermercado/{slug}/{cat_id}/c",
                callback=self.parse_category,
                meta={"slug": slug, "cat_id": cat_id, "offset": 0},
            )

    def parse_category(self, response):
        slug = response.meta["slug"]
        cat_id = response.meta["cat_id"]
        offset = response.meta["offset"]

        data = _parse_initial_state(response.text)
        if data is None:
            logger.warning("carrefour_es: no __INITIAL_STATE__ on %s", response.url)
            return

        try:
            results = data["productCardList"]["results"]
        except (KeyError, TypeError):
            logger.warning("carrefour_es: unexpected shape on %s", response.url)
            return

        items = results.get("items") or []
        total_results = (results.get("pagination") or {}).get("total_results") or 0
        logger.info(
            "carrefour_es: %s offset=%d -> %d items (total_results=%s)",
            slug,
            offset,
            len(items),
            total_results,
        )

        for entry in items:
            item = self._item(entry, slug)
            if item:
                yield item

        next_offset = offset + _PAGE_SIZE
        if items and next_offset < total_results and next_offset < MAX_OFFSET_PER_CATEGORY:
            yield scrapy.Request(
                f"{_BASE}/supermercado/{slug}/{cat_id}/c?offset={next_offset}",
                callback=self.parse_category,
                meta={"slug": slug, "cat_id": cat_id, "offset": next_offset},
            )

    def _item(self, entry, slug):
        name = entry.get("name")
        price = _parse_price(entry.get("price"))
        if not name or not price:
            return None

        rel_url = entry.get("url") or ""
        url = f"{_BASE}{rel_url}" if rel_url.startswith("/") else rel_url

        return {
            "product_id": entry.get("product_id") or entry.get("sku_id") or url,
            "product_name": str(name).strip()[:500],
            "category": slug,
            "price": price,
            "currency": self.currency,
            "available": (entry.get("units_in_stock") or 0) > 0,
            "url": url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
