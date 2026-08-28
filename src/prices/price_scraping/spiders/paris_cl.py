"""
Spider for Paris.cl (Chile department store, Cencosud group) --
https://www.paris.cl/.

Next.js App Router storefront. The visible product grid is client-hydrated
(tailwind-obfuscated, no stable CSS classes), but each category page also
server-renders a WebPage/ItemList JSON-LD block -- not as a plain
`<script type="application/ld+json">` tag, but escaped inside one of the
page's `self.__next_f.push([1, "..."])` RSC stream chunks. Decoding that
chunk (JSON-string-of-a-JSON-string: `json.loads` twice) yields
`mainEntity.itemListElement`, each a `ListItem` wrapping a schema.org
`Product` with clean name/url/sku/offers.price/offers.priceCurrency.

Caveat verified live: the `?page=N` query param the site's own pagination
links use does NOT change the server-rendered JSON-LD (page 2 returns the
same 30 items as page 1 -- pagination past the first page is client-side
only, fetched from an API this plain-HTTP crawl can't see). So this spider
is scoped breadth-first across many leaf categories (each contributing its
first ~30 products) rather than depth-first paginating one category, which
is the only way to get real SSR coverage without inventing an
unverified API tier.

66 leaf/department URLs below were discovered by fetching 7 top-level
department pages (tecnologia, mujer, hombre, belleza, deportes, dormitorio,
supermercado) and regex-scanning each for its own `/<dept>/<subcat>/` nav
links.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.paris.cl"

CATEGORY_PATHS = [
    "/tecnologia/",
    "/tecnologia/accesorios-computacion/",
    "/tecnologia/accesorios-fotografia/",
    "/tecnologia/celulares/",
    "/tecnologia/computadores/",
    "/tecnologia/consolas-videojuegos/",
    "/tecnologia/fotografia/",
    "/tecnologia/gamers/",
    "/tecnologia/impresoras/",
    "/tecnologia/marcas/",
    "/tecnologia/ofertas/",
    "/tecnologia/smart-home/",
    "/tecnologia/wearables/",
    "/mujer/",
    "/mujer/accesorios-moda/",
    "/mujer/colecciones/",
    "/mujer/marcas/",
    "/mujer/moda/",
    "/mujer/novedades/",
    "/mujer/ofertas/",
    "/mujer/ropa-interior/",
    "/mujer/zapatos/",
    "/hombre/",
    "/hombre/accesorios/",
    "/hombre/cuidado-personal/",
    "/hombre/marcas/",
    "/hombre/moda/",
    "/hombre/novedades/",
    "/hombre/ofertas/",
    "/hombre/ropa-interior/",
    "/hombre/zapatos/",
    "/belleza/",
    "/deportes/",
    "/deportes/acuaticos/",
    "/deportes/aire-libre/",
    "/deportes/bicicletas/",
    "/deportes/camping/",
    "/deportes/especificos/",
    "/deportes/fitness/",
    "/deportes/hombre/",
    "/deportes/marcas/",
    "/deportes/motocicletas/",
    "/deportes/movilidad-electrica/",
    "/deportes/mujer/",
    "/deportes/ninos/",
    "/deportes/novedades/",
    "/deportes/ofertas/",
    "/deportes/outdoor/",
    "/deportes/outlet-deportes/",
    "/deportes/ropa-deportiva/",
    "/deportes/suplementos-deportivos/",
    "/deportes/zapatillas/",
    "/dormitorio/",
    "/dormitorio/box-spring/",
    "/dormitorio/camas-americanas/",
    "/dormitorio/camas-colchones/",
    "/dormitorio/camas-europeas/",
    "/dormitorio/camas-funcionales/",
    "/dormitorio/camas-plazaje/",
    "/dormitorio/colchones/",
    "/dormitorio/combos/",
    "/dormitorio/marcas/",
    "/dormitorio/muebles/",
    "/dormitorio/ninos/",
    "/dormitorio/outlet-dormitorio/",
    "/dormitorio/ropa-cama/",
    "/supermercado/",
    "/supermercado/cervezas-vinos-y-licores/",
    "/supermercado/despensa/",
    "/supermercado/higiene-y-cuidado-personal/",
    "/supermercado/productos-limpieza/",
]

CHUNK_RE = re.compile(r'<script>self\.__next_f\.push\(\[1,(".*?")\]\)</script>', re.S)


def _extract_items(response_text: str):
    for m in CHUNK_RE.finditer(response_text):
        raw = m.group(1)
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if "itemListElement" not in decoded:
            continue
        try:
            data = json.loads(decoded)
        except json.JSONDecodeError:
            continue
        main = data.get("mainEntity") or {}
        items = main.get("itemListElement") or []
        if items:
            return items
    return []


class ParisClSpider(scrapy.Spider):
    name = "paris_cl"
    allowed_domains = ["paris.cl", "www.paris.cl"]
    currency = "CLP"
    language = "es"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.total_items = 0

    async def start(self):
        for path in CATEGORY_PATHS:
            yield scrapy.Request(
                f"{_BASE}{path}", callback=self.parse_category, meta={"path": path}
            )

    def parse_category(self, response):
        path = response.meta["path"]
        category = " > ".join(p for p in path.strip("/").split("/") if p)
        items = _extract_items(response.text)
        n = 0
        for entry in items:
            product = entry.get("item") or {}
            offers = product.get("offers") or {}
            name = product.get("name")
            sku = product.get("sku")
            price = offers.get("price")
            if not name or not sku or price is None:
                continue
            n += 1
            self.total_items += 1
            yield {
                "product_id": str(sku),
                "product_name": name[:500],
                "category": category,
                "price": str(price),
                "currency": offers.get("priceCurrency", self.currency),
                "available": "InStock" in (offers.get("availability") or ""),
                "url": product.get("url") or response.url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        logger.info(f"paris_cl: {response.url} candidates={len(items)} items={n}")

    def closed(self, reason):
        if self.total_items == 0:
            logger.error(
                f"paris_cl: crawl finished (reason={reason}) with ZERO items -- "
                "the RSC chunk shape likely changed, do not ship."
            )
