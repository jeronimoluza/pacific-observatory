"""
Spider for Ananas (Serbia) - ananas.rs, a multi-vendor e-commerce marketplace
(sellers onboard via academy.ananas.rs/prodaj-na-ananasu).

Next.js SSR. Top-level category pages (/kategorije/<slug>) carry no
products, only subcategory tiles; products live on the 208 leaf
subcategory pages (/kategorije/<top>/<sub>?page=N), each of which embeds a
`<script id="category-product-schema" type="application/ld+json">` Schema.org
ItemList of up to 12 Products (name/url/offers.price/offers.priceCurrency)
server-side. `numberOfItems` gives the category total; pagination is plain
`?page=N` and the first page past the last one has an empty (or missing)
itemListElement (verified on hrana-i-pice/kafa: 553 items over 47 pages,
page 48 empty), so the spider stops on an empty/missing list.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://ananas.rs"

_LEAF_CATEGORIES = [
    "aparati-za-negu-i-lepotu/aparati-za-brijanje-i-oprema",
    "aparati-za-negu-i-lepotu/aparati-za-kosu",
    "aparati-za-negu-i-lepotu/aparti-za-negu-lica-i-tela",
    "auto-i-moto/audio-i-video-za-vozila",
    "auto-i-moto/auto-kozmetika",
    "auto-i-moto/auto-oprema-i-odrzavanje",
    "auto-i-moto/gume",
    "auto-i-moto/moto-oprema",
    "bela-tehnika/aspiratori",
    "bela-tehnika/bojleri",
    "bela-tehnika/dodatna-oprema-za-belu-tehniku",
    "bela-tehnika/frizideri",
    "bela-tehnika/grejna-tela",
    "bela-tehnika/klima-uredjaji",
    "bela-tehnika/masine-za-pranje-sudova",
    "bela-tehnika/mikrotalasne-rerne",
    "bela-tehnika/preciscivaci-vazduha",
    "bela-tehnika/rashladne-i-vinske-vitrine",
    "bela-tehnika/sporeti-rerne-i-ploce",
    "bela-tehnika/sredstva-za-ciscenje-i-zastitu-tehnike",
    "bela-tehnika/ves-masine",
    "bela-tehnika/zamrzivaci",
    "decija-oprema/auto-sedista-za-decu-i-bebe",
    "decija-oprema/bebi-apoteka",
    "decija-oprema/bebi-soba",
    "decija-oprema/hrana-za-bebe",
    "decija-oprema/kolica-za-bebe-i-dodaci",
    "decija-oprema/kozmetika-za-bebe",
    "decija-oprema/obuca-za-bebe",
    "decija-oprema/odeca-i-aksesoari-za-bebe",
    "decija-oprema/oprema-za-bebe",
    "decija-oprema/oprema-za-hranjenje-beba",
    "decija-oprema/pelene-i-maramice",
    "decija-oprema/proizvodi-za-mame",
    "domaci-tradicionalni-proizvodi/etno-garderoba",
    "gaming",
    "hrana-i-pice/caj",
    "hrana-i-pice/kafa",
    "hrana-i-pice/konzervirana-hrana-supe-i-gotova-jela",
    "hrana-i-pice/pice",
    "hrana-i-pice/priprema-jela",
    "hrana-i-pice/slatkisi-i-grickalice",
    "hrana-i-pice/zdrava-hrana",
    "igracke",
    "ishrana-i-zdravlje",
    "it-shop",
    "kancelarijski-i-skolski-pribor",
    "knjizara-i-zabava",
    "kuca-i-basta",
    "lepota-i-nega",
    "mali-kucni-aparati",
    "moda",
    "muzicki-instrumenti-i-oprema",
    "odrzavanje-kuce",
    "pet-shop",
    "poklon-kartice",
    "sport-i-rekreacija",
    "telefoni-i-foto",
    "tv-audio-i-video",
    "uradi-sam",
]

_SCHEMA_RE = re.compile(
    r'<script id="category-product-schema" type="application/ld\+json">(.*?)</script>',
    re.DOTALL,
)
_MAX_PAGES = 120


class AnanasRsSpider(scrapy.Spider):
    name = "ananas_rs"
    allowed_domains = ["ananas.rs"]
    currency = "RSD"
    language = "sr"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
    }

    async def start(self):
        for slug in _LEAF_CATEGORIES:
            yield scrapy.Request(
                f"{_BASE}/kategorije/{slug}?page=1",
                callback=self.parse_list,
                cb_kwargs={"slug": slug, "page": 1},
            )

    def parse_list(self, response, slug, page):
        match = _SCHEMA_RE.search(response.text)
        if not match:
            logger.info("ananas_rs: %s page %d has no schema, stopping", slug, page)
            return
        try:
            data = json.loads(match.group(1))
        except (ValueError, TypeError):
            return
        items = data.get("itemListElement") or []
        if not items:
            logger.info("ananas_rs: %s page %d empty, stopping", slug, page)
            return

        for product in items:
            if not isinstance(product, dict):
                continue
            name = product.get("name")
            url = product.get("url")
            offers = product.get("offers") or {}
            price = offers.get("price")
            if not (name and url and price not in (None, "", 0)):
                continue
            product_id = url.rstrip("/").rsplit("/", 1)[-1]
            yield {
                "product_id": product_id,
                "product_name": str(name).strip()[:500],
                "category": slug,
                "price": str(price),
                "currency": offers.get("priceCurrency") or self.currency,
                "available": True,
                "url": url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        if page >= _MAX_PAGES:
            logger.warning("ananas_rs: %s hit page cap %d", slug, _MAX_PAGES)
            return

        next_page = page + 1
        yield scrapy.Request(
            f"{_BASE}/kategorije/{slug}?page={next_page}",
            callback=self.parse_list,
            cb_kwargs={"slug": slug, "page": next_page},
        )
