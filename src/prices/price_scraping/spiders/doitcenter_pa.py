"""
Spider for Do it Center (Panama) -- https://www.doitcenter.com.pa/.

Home-improvement / general-merchandise chain, Next.js storefront (Webscale
platform; Magento REST path 301s to the homepage so that's a dead end).
Category grid is fully server-rendered -- Algolia-backed (per CSP) but the
first page of results ships inline in the HTML, no JS execution needed.
Product tiles use CSS-module classnames with build hashes
(`ProductTile_product-name__6gpDO`) for structural wrappers, but the
price/sku leaf classes are plain, un-hashed utility classes
(`product-price--value`, `product-sku`) -- selectors below match on the
stable un-hashed classes plus `[class*=...]` for the hashed wrappers, so a
hash rotation on redeploy won't break this.

Re-verified live 2026-08-17: GET /categorias/automovil -> 200, 48
products/page, "totalPages":43 embedded in the page JSON; real USD prices
e.g. "Hidrolavadora Electrica 2000 Psi 1600W" JET MATE $49.99 (regular
$89.99, -44% badge). Pagination is `?page=N`.
"""

from datetime import datetime, timezone
from typing import Iterator
from urllib.parse import urljoin

import scrapy

from ..archived import row_from_meta, rows_from_jsonld

_BASE = "https://www.doitcenter.com.pa"
_CATEGORIES = [
    "abanicos",
    "automovil",
    "banos",
    "bouclair",
    "cocina",
    "construccion",
    "decoracion",
    "deportes",
    "electricidad",
    "electronica",
    "ferreteria",
    "focos",
    "herramientas",
    "jardin",
    "lamparas",
    "linea-blanca",
    "mascotas",
    "muebles",
    "organizacion-y-limpieza",
    "pintura",
    "plomeria",
    "recamara",
    "salud-y-bienestar",
    "servicios-y-comestibles",
    "vida-exterior",
]
MAX_PAGES_PER_CATEGORY = 15


class DoitcenterPaSpider(scrapy.Spider):
    name = "doitcenter_pa"
    allowed_domains = ["doitcenter.com.pa"]
    currency = "USD"
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
        for slug in _CATEGORIES:
            yield scrapy.Request(
                f"{_BASE}/categorias/{slug}",
                callback=self.parse_category,
                meta={"slug": slug, "page": 1},
            )

    def parse_category(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]
        tiles = response.css("div.productitem-block")
        for tile in tiles:
            href = tile.css("a::attr(href)").get()
            if not href:
                continue
            brand = (tile.css('[class*="brand-name"]::text').get() or "").strip()
            name = (tile.css('[class*="productname-link"]::text').get() or "").strip()
            full_name = f"{brand} {name}".strip() if brand else name
            if not full_name:
                continue
            price = (tile.css("span.product-price--value::text").get() or "").strip()
            price = price.lstrip("$").replace(",", "").strip()
            if not price:
                continue
            product_id = (
                tile.attrib.get("data-insights-object-id")
                or (tile.css("span.product-sku::text").get() or "").strip()
                or href
            )
            yield {
                "product_id": str(product_id),
                "product_name": full_name[:500],
                "category": slug,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": urljoin(_BASE, href),
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        if tiles and page < MAX_PAGES_PER_CATEGORY:
            yield scrapy.Request(
                f"{_BASE}/categorias/{slug}?page={page + 1}",
                callback=self.parse_category,
                meta={"slug": slug, "page": page + 1},
            )

    # ------------------------------------------------------------------
    # Crawl backfiller (prices/backfill.py's parse_html hook). Archived
    # snapshots here are individual /productos/<slug> PDPs (a different
    # page from the /categorias/<slug> listings the live crawl walks), but
    # confirmed live 2026-08-18 on 2 PDPs: this Webscale/Next.js theme
    # emits a full Product JSON-LD block, so the shared jsonld tier covers
    # this spider on its own (the OpenGraph meta tier also works here as a
    # fallback, but its product_name carries a " | Do it Center" suffix
    # jsonld's does not).
    # ------------------------------------------------------------------
    @classmethod
    def parse_html(cls, html_text: str, url: str) -> Iterator[dict]:
        """Parse one archived Do it Center PDP page."""
        rows = rows_from_jsonld(html_text, url)
        if not rows:
            row = row_from_meta(html_text, url)
            rows = [row] if row else []
        for row in rows:
            row.setdefault("currency", cls.currency)
            row.setdefault("language", cls.language)
            yield row
