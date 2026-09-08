"""
Encuentra24 (Panama) -- https://www.encuentra24.com/panama-es.

Regional (Central America-wide) classifieds marketplace; this spider
covers only the Panama storefront (`/panama-es/...`). Server-rendered
Next.js pages, no anti-bot -- plain curl_cffi clears every category and
paginated page at 200.

A curated set of top-level category paths is walked directly (not
crawled via link-following) so that non-priced categories (job postings,
courses, "yo busco"/want-ads) are excluded up front. Each category
paginates via a `.<N>` URL suffix (`/bienes-raices-alquiler`,
`/bienes-raices-alquiler.2`, ...); verified live 2026-09-06 that page 1
and page 2 of `bienes-raices-alquiler` return zero id overlap (20 listings
each) -- genuine pagination.

Every listing card shares one site-wide component template regardless of
category (spot-checked on both bienes-raices-alquiler and autos-usados):

    <a href="<permalink-with-trailing-numeric-id>" ... class="... item-card-link">
      ...
      <h3 class="card_title ...">Title</h3>
      ...
      <span class="card_price ...">$ 1,599</span>   (React renders this as
                                                       "$"/" "/"1,599" split
                                                       across <!-- --> HTML
                                                       comment placeholders,
                                                       stripped before parsing)

Panama prices are quoted in US dollars (Panama's other legal tender is
the PAB balboa, pegged 1:1 to USD and not separately displayed on this
site) -- `$` is treated as USD, matching countries.yaml.

`bienes-raices-alquiler` (real-estate rentals) is the standout find here:
COICOP 04.1.1 asking rents, a division most retailer-SKU sources never
touch. Sale-of-property categories are deliberately excluded (not a
consumption price); "busco"/"yo busco" (want-to-buy/want-a-job) rows have
no seller-set price and are skipped by the parser (no `card_price` match).
"""

import logging
import re

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.encuentra24.com"

# Curated top-level Panama categories with real seller-set prices --
# excludes jobs (empleos*), courses (cursos-clases-seminarios*), and
# property-for-sale (bienes-raices-venta-de-propiedades*, not a
# consumption price).
_CATEGORY_PATHS = [
    "/panama-es/bienes-raices-alquiler",
    "/panama-es/bienes-raices-alquiler-apartamentos",
    "/panama-es/bienes-raices-alquiler-casas",
    "/panama-es/bienes-raices-alquiler-cuartos",
    "/panama-es/autos-usados",
    "/panama-es/autos-nuevos",
    "/panama-es/autos-motos",
    "/panama-es/electronica-telefono-movil",
    "/panama-es/electronica-computadora-oficina-computadoras-accesorios",
    "/panama-es/anuncios-clasificados-electrodomesticos-electrodomesticos",
    "/panama-es/anuncios-casificados-muebles-hogar-y-jardin-muebles",
]

MAX_PAGES_PER_CAT = 5  # safety cap: ~100 listings/category

_CARD_SPLIT_RE = re.compile(
    r'<a href="(/panama-es/[^"]+)" target="_blank" class="block h-full w-full item-card-link">'
)
_TITLE_RE = re.compile(r'card_title[^"]*">([^<]+)</h3>')
_PRICE_RE = re.compile(r'<span class="card_price\s[^"]*">(.*?)</span>', re.S)
_PRICE_VAL_RE = re.compile(r"\$\s*([\d,]+)")


class Encuentra24PaSpider(scrapy.Spider):
    name = "encuentra24_pa"
    allowed_domains = ["encuentra24.com"]
    currency = "USD"
    language = "es"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
        "DOWNLOAD_TIMEOUT": 60,
    }

    async def start(self):
        for path in _CATEGORY_PATHS:
            yield scrapy.Request(
                _BASE + path,
                callback=self.parse_category,
                meta={"path": path, "page": 1},
            )

    def parse_category(self, response):
        path = response.meta["path"]
        page = response.meta["page"]
        parts = _CARD_SPLIT_RE.split(response.text)
        found = 0
        for i in range(1, len(parts), 2):
            href = parts[i]
            content = parts[i + 1] if i + 1 < len(parts) else ""
            item = self._item(href, content)
            if item:
                found += 1
                yield item
        logger.info(f"{self.name}: {path} page={page} listings={found}")

        if found > 0 and page < MAX_PAGES_PER_CAT:
            next_page = page + 1
            yield scrapy.Request(
                f"{_BASE}{path}.{next_page}",
                callback=self.parse_category,
                meta={"path": path, "page": next_page},
            )

    def _item(self, href, content):
        title_m = _TITLE_RE.search(content)
        price_m = _PRICE_RE.search(content)
        if not (title_m and price_m):
            return None
        price_text = re.sub(r"<!--\s*-->", "", price_m.group(1)).strip()
        val_m = _PRICE_VAL_RE.search(price_text)
        if not val_m:
            return None
        try:
            price = float(val_m.group(1).replace(",", ""))
        except ValueError:
            return None
        if price <= 0:
            return None

        listing_id_m = re.search(r"/(\d+)$", href)
        return {
            "product_id": listing_id_m.group(1) if listing_id_m else None,
            "product_name": title_m.group(1).strip()[:500],
            "price": str(price),
            "currency": self.currency,
            "category": None,
            "url": _BASE + href,
            "available": True,
            "language": self.language,
        }
