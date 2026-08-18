"""
Spider for Precios del Super (Spain) — https://preciosdelsuper.es/.

Independent price-tracking aggregator that scrapes several Spanish
supermarket chains (DIA, Carrefour, Mercadona, etc. — product image domains
reveal the source retailer, e.g. dia.es) and republishes name/price/history.
Custom SSR site, no WAF.

The homepage's "hero" widgets are only small highlight carousels (confirmed
in round 1). The real catalog walk is the `/nuevos` (new products) feed:
`<script type="application/ld+json">` on that page declares
`"numberOfItems": 138075` and the page paginates with `?page=N` up to
`page=6904` (20 products/page * 6904 ~= 138075, i.e. the feed IS effectively
a full paginated catalog walk in date-added order). Each product card is
server-rendered: `<a href="/producto/<slug>" ...><p class="product-name">
NAME</p> ... <strong class="main-color product-price-tag">PRICE€</strong>`.

Re-verified live 2026-08-06: GET /nuevos?page=2 -> 200, 269KB, 20 real
products incl. 'Compresa con alas Cottonlike Super Plus Evax 20 unidades',
'Moras ecológicas categoría 1a bandeja 125 g', 'Uva Cotton Candy categoría
1a bandeja 300 g'. Retailer is not itself first-party — this republishes
several supermarkets' catalogs, so `channel: marketplace` and no single
`currency` mismatch risk (site is EUR-only, matches countries.yaml for
Spain).
"""

import html
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://preciosdelsuper.es"
MAX_PAGES = 300  # safety cap; full feed is ~6900 pages

_CARD_RE = re.compile(
    r'href="(/producto/[a-z0-9-]+)" class="text-decoration-none">.*?'
    r'<p class="product-name[^"]*">\s*([^<]+?)\s*</p>.*?'
    r'product-price-tag">([0-9]+,[0-9]{2})€',
    re.S,
)


class PreciosdelsuperEsSpider(scrapy.Spider):
    name = "preciosdelsuper_es"
    allowed_domains = ["preciosdelsuper.es"]
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
        yield scrapy.Request(
            f"{_BASE}/nuevos?page=1", callback=self.parse_page, meta={"page": 1}
        )

    def parse_page(self, response):
        page = response.meta["page"]
        cards = _CARD_RE.findall(response.text)
        logger.info(f"preciosdelsuper_es: page={page} count={len(cards)}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for url_path, name, price in cards:
            product_id = url_path.rsplit("/", 1)[-1]
            yield {
                "product_id": product_id,
                "product_name": html.unescape(name).strip()[:500],
                "category": "nuevos",
                "price": price.replace(",", "."),
                "currency": self.currency,
                "available": True,
                "url": f"{_BASE}{url_path}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        if cards and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{_BASE}/nuevos?page={nxt}",
                callback=self.parse_page,
                meta={"page": nxt},
            )
