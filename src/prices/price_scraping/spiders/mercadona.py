"""
Spider for Mercadona (Spain) — https://tienda.mercadona.es/.

Public JSON API, no auth. GET /api/categories/ returns 26 top-level groups,
each with a nested list of leaf subcategories (id, name). GET
/api/categories/{leaf_id}/ then returns that leaf's own nested
sub-subcategories, each carrying a `products` list in one shot (no further
pagination inside a category). We walk all ~151 leaf ids found under the
top-level groups.

Re-verified live 2026-08-06: /api/categories/ -> 200, 26 groups / 151 leaf
ids. /api/categories/112/ (Aceite, vinagre y sal) -> 200, real product
'Aceite de oliva 0,4º Hacendado' (Garrafa), price_instructions.bulk_price
"3.55" EUR — bulk_price is the shelf price actually charged; unit_price is
the per-kg/per-l reference price. Product names are Spanish.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://tienda.mercadona.es/api"


class MercadonaSpider(scrapy.Spider):
    name = "mercadona"
    allowed_domains = ["tienda.mercadona.es"]
    currency = "EUR"
    language = "es"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(f"{_BASE}/categories/", callback=self.parse_top)

    def parse_top(self, response):
        try:
            data = response.json()
        except ValueError:
            logger.error("mercadona: non-JSON at /api/categories/")
            return
        leaf_ids = set()
        for top in data.get("results") or []:
            for sub in top.get("categories") or []:
                if sub.get("id"):
                    leaf_ids.add(sub["id"])
        logger.info(f"mercadona: {len(leaf_ids)} leaf categories to walk")
        for cid in leaf_ids:
            yield scrapy.Request(
                f"{_BASE}/categories/{cid}/",
                callback=self.parse_category,
                meta={"category_id": cid},
            )

    def parse_category(self, response):
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"mercadona: non-JSON at {response.url}")
            return
        scraped_at = datetime.now(timezone.utc).isoformat()
        yield from self._walk(data, data.get("name"), scraped_at)

    def _walk(self, node, category_name, scraped_at):
        for p in node.get("products") or []:
            item = self._item(p, category_name, scraped_at)
            if item:
                yield item
        for sub in node.get("categories") or []:
            yield from self._walk(sub, sub.get("name") or category_name, scraped_at)

    def _item(self, p, category_name, scraped_at):
        instr = p.get("price_instructions") or {}
        price = instr.get("bulk_price")
        name = p.get("display_name")
        if not name or price is None:
            return None
        share_url = p.get("share_url") or ""
        return {
            "product_id": str(p.get("id") or ""),
            "product_name": name.strip()[:500],
            "category": category_name,
            "price": str(price),
            "currency": self.currency,
            "available": bool(p.get("published", True)),
            "url": share_url,
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
