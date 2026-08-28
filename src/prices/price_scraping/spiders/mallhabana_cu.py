"""
Spider for Mallhabana (Cuba diaspora grocery-delivery site) -- https://mallhabana.com/.

Server-rendered PrestaShop storefront, but this theme drops the schema.org
[itemtype$="/Product"] microdata the shared `_prestashop_base.py` relies on
(verified live: zero `itemtype` matches on a category page that clearly has
products) -- product cards there instead use a bare `article.product-miniature
[data-id-product]` container, `h2.product-title a` for name+URL and
`span.price` for price. Standalone spider rather than a base-class subclass
because the base's container selector cannot match this theme without
editing the shared base (disallowed).

Prices are USD, not the diaspora-guessed generic "$": the category page's
inline PrestaShop JS config carries `"currency":{"iso_code":"USD", ...}`
and `body_classes` includes `currency-USD`. Site sells to buyers abroad who
pay in USD for delivery to Cuba.

75 categories collected from the homepage nav (deduped by numeric id);
category pages are also scanned for further `id-slug` links in case any
subcategory isn't in the top nav. Pagination is `?page=N`.
"""

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://mallhabana.com"
MAX_PAGES = 15

CATEGORY_HREF_RE = re.compile(r'href="(https://mallhabana\.com/(\d+)-[a-z0-9\-]+/?)"')
SKIP_URL_RE = re.compile(
    r"/(cart|carrito|login|iniciar-sesion|cuenta|account|contact|contacto|cms|"
    r"content|direccion|address|newsletter|module|sitemap|busqueda|search|"
    r"pedido|order)[/-]",
    re.IGNORECASE,
)

START_CATEGORIES = [
    "https://mallhabana.com/76-supermercado-envios-a-cuba-mallhabana",
    "https://mallhabana.com/77-alimentos-envios-a-cuba-mallhabana",
    "https://mallhabana.com/79-aceites-salsas-condimentos-envios-a-cuba-mallhabana",
    "https://mallhabana.com/84-aperitivos-envios-a-cuba-mallhabana",
    "https://mallhabana.com/78-conservas",
    "https://mallhabana.com/82-desayunos-meriendas-envios-a-cuba-mallhabana",
    "https://mallhabana.com/83-frutas-verduras-viandas-envios-a-cuba-mallhabana",
    "https://mallhabana.com/80-granos-envios-a-cuba-mallhabana",
    "https://mallhabana.com/81-pastas-sopas-cremas-envios-a-cuba-mallhabana",
    "https://mallhabana.com/618-carnes-pescados-envios-a-cuba-mallhabana",
    "https://mallhabana.com/622-carne-aves-envios-a-cuba-mallhabana",
    "https://mallhabana.com/623-carne-cerdo-res-envios-a-cuba-mallhabana",
    "https://mallhabana.com/625-embutidos-envios-a-cuba-mallhabana",
    "https://mallhabana.com/624-pescados-mariscos-envios-a-cuba-mallhabana",
    "https://mallhabana.com/619-quesos-lacteos-envios-a-cuba-mallhabana",
    "https://mallhabana.com/617-bebidas-envios-a-cuba-mallhabana",
    "https://mallhabana.com/626-aguas-refrescos-envios-a-cuba-mallhabana",
    "https://mallhabana.com/628-cervezas-maltas-envios-a-cuba-mallhabana",
    "https://mallhabana.com/627-jugos-envios-a-cuba-mallhabana",
    "https://mallhabana.com/629-vinos-licores-envios-a-cuba-mallhabana",
    "https://mallhabana.com/648-utiles-del-hogar",
    "https://mallhabana.com/649-productos-lavado-de-ropa-envios-a-cuba-mallhabana",
    "https://mallhabana.com/650-limpieza-del-hogar-envios-a-cuba-mallhabana",
    "https://mallhabana.com/652-papel-envios-a-cuba-mallhabana",
    "https://mallhabana.com/630-combos-productos-envios-a-cuba-mallhabana",
    "https://mallhabana.com/653-belleza-salud-envios-a-cuba-mallhabana",
    "https://mallhabana.com/655-aseo-y-bano-envios-a-cuba-mallhabana",
    "https://mallhabana.com/657-productos-cabello-envios-a-cuba-mallhabana",
    "https://mallhabana.com/656-cosmetica-envios-a-cuba-mallhabana",
    "https://mallhabana.com/660-parafarmacia-envios-a-cuba-mallhabana",
    "https://mallhabana.com/658-perfumes-colonias-envios-a-cuba-mallhabana",
    "https://mallhabana.com/631-combos-nacionales",
    "https://mallhabana.com/636-electrodomesticos-envios-a-cuba-mallhabana",
    "https://mallhabana.com/639-electrodomesticos-importados-envios-a-cuba-mallhabana",
    "https://mallhabana.com/646-grandes-electrodomesticos-importados-envios-a-cuba-mallhabana",
    "https://mallhabana.com/647-pequenos-electrodomesticos-importados-envios-a-cuba-mallhabana",
    "https://mallhabana.com/637-grandes-electrodomesticos-envios-a-cuba-mallhabana",
    "https://mallhabana.com/640-equipos-climatizacion-envios-a-cuba-mallhabana",
    "https://mallhabana.com/643-cocinas-hornos-y-campanas",
    "https://mallhabana.com/644-lavadoras-y-secadoras",
    "https://mallhabana.com/645-refrigeradores-neveras-envios-a-cuba-mallhabana",
    "https://mallhabana.com/641-televisores",
    "https://mallhabana.com/638-pequenos-electrodomesticos-envios-a-cuba-mallhabana",
    "https://mallhabana.com/671-hogar-envios-a-cuba-mallhabana",
    "https://mallhabana.com/674-articulos-bano-envios-a-cuba-mallhabana",
    "https://mallhabana.com/675-dormitorio-envios-a-cuba-mallhabana",
    "https://mallhabana.com/677-colchones-envios-a-cuba-mallhabana",
    "https://mallhabana.com/706-jardin-terraza-envios-a-cuba-mallhabana",
    "https://mallhabana.com/673-salon-comedor-envios-a-cuba-mallhabana",
    "https://mallhabana.com/676-productos-textiles-envios-a-cuba-mallhabana",
    "https://mallhabana.com/672-utiles-cocina-envios-a-cuba-mallhabana",
    "https://mallhabana.com/678-productos-ninos-bebe-envios-a-cuba-mallhabana",
    "https://mallhabana.com/661-para-regalar-envios-a-cuba-mallhabana",
    "https://mallhabana.com/716-calzado-envios-a-cuba-mallhabana",
    "https://mallhabana.com/666-comida-a-domicilio-cuba-mallhabana",
    "https://mallhabana.com/664-dulceria-envios-a-cuba-mallhabana",
    "https://mallhabana.com/665-floristeria-envios-a-cuba-mallhabana",
    "https://mallhabana.com/684-oficina-papeleria-envios-a-cuba-mallhabana",
    "https://mallhabana.com/663-productos-panaderia-envios-a-cuba-mallhabana",
    "https://mallhabana.com/662-regalar-envios-a-cuba-mallhabana",
    "https://mallhabana.com/668-ferreteria",
    "https://mallhabana.com/707-herramientas-envios-a-cuba-mallhabana",
    "https://mallhabana.com/651-limpieza-industrial-piscinas-envios-a-cuba-mallhabana",
    "https://mallhabana.com/695-materiales-construccion-envios-a-cuba-mallhabana",
    "https://mallhabana.com/670-pinturas-envios-a-cuba-mallhabana",
    "https://mallhabana.com/679-accesorios-repuestos-motos-automoviles-envios-a-cuba-mallhabana",
    "https://mallhabana.com/687-aditivos-y-lubricantes",
    "https://mallhabana.com/696-baterias",
    "https://mallhabana.com/702-chapisteria-y-pintura",
    "https://mallhabana.com/700-herramientas-automoviles-envios-a-cuba-mallhabana",
    "https://mallhabana.com/688-llantas-y-neumaticos",
    "https://mallhabana.com/701-motor-y-trasmision",
    "https://mallhabana.com/686-partes-piezas-y-accesorios",
    "https://mallhabana.com/691-sistema-de-audio",
    "https://mallhabana.com/718-ofertas-mh",
]


def _normalize_price(raw: str) -> str | None:
    if not raw:
        return None
    s = re.sub(r"[^\d,.]", "", raw)
    if not s:
        return None
    if "," in s and "." in s:
        if s.rindex(",") > s.rindex("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".") if s.count(",") == 1 else s.replace(",", "")
    try:
        float(s)
    except ValueError:
        return None
    return s


class MallhabanaCuSpider(scrapy.Spider):
    name = "mallhabana_cu"
    allowed_domains = ["mallhabana.com"]
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_categories: set[str] = {
            m.group(1) for url in START_CATEGORIES for m in [re.search(r"/(\d+)-", url)]
        }
        self.total_items = 0

    async def start(self):
        for url in START_CATEGORIES:
            yield scrapy.Request(url, callback=self.parse_category, meta={"page": 1})

    def _new_category_requests(self, response):
        for url, cat_id in CATEGORY_HREF_RE.findall(response.text):
            if cat_id in self.seen_categories or SKIP_URL_RE.search(url):
                continue
            self.seen_categories.add(cat_id)
            yield scrapy.Request(url, callback=self.parse_category, meta={"page": 1})

    def parse_category(self, response):
        yield from self._new_category_requests(response)

        cards = response.css("article.product-miniature")
        page = response.meta["page"]
        h1 = response.css("h1::text").get()
        category = h1.strip() if h1 else None
        n = 0
        for card in cards:
            product_id = card.attrib.get("data-id-product")
            link = card.css("h2.product-title a")
            name = link.css("::text").get()
            href = link.attrib.get("href")
            price_text = card.css("span.price::text").get()
            price = _normalize_price(price_text)
            if not product_id or not name or not href or not price:
                continue
            n += 1
            self.total_items += 1
            yield {
                "product_id": product_id,
                "product_name": name.strip()[:500],
                "category": category,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": urljoin(response.url, href),
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        logger.info(
            f"mallhabana_cu: {response.url} page={page} cards={len(cards)} items={n}"
        )

        if cards and page < MAX_PAGES:
            base = response.url.split("?")[0]
            yield scrapy.Request(
                f"{base}?page={page + 1}",
                callback=self.parse_category,
                meta={"page": page + 1},
            )

    def closed(self, reason):
        if self.total_items == 0:
            logger.error(
                f"mallhabana_cu: crawl finished (reason={reason}) with ZERO items -- "
                "selectors likely stale, do not ship."
            )
