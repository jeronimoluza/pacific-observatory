"""
Spider for Pacifiko (Guatemala electronics/appliances retailer) --
https://www.pacifiko.com/.

CSV listed the platform as VTEX by URL shape, but `/api/catalog_system/pub/
products/search` 301-redirects to the homepage -- red herring. Re-verification
found a genuine OpenCart backend (`index.php?route=product/category&path=...`
URLs alongside SEO-clean category slugs), but on a heavily customized
"so-emarket" theme: cards are `div.product-layout` (no `product-thumb` class
at all, matching the shared `_opencart_base.py`'s fallback), but name/price
markup doesn't match any of that base's NAME_SELECTORS/PRICE_SELECTORS --
there's no `.caption`/`.content h4` at all. Instead each card carries the
full product name directly as a `data-name` attribute and the numeric
product id as the card's own `id` attribute, which is more reliable than
scraping visible text anyway. Standalone spider rather than editing the
shared base.

Category entry points are a curated list: 18 SEO-clean slugs found in the
homepage megamenu, plus 3 additional `path=` category ids (Celulares y
Accesorios, Electrodomesticos, Termos y Pachones) surfaced only via the
classic `route=product/category` URL and not linked as clean slugs. No
sitemap.xml or robots.txt is reachable (both 403 from a CloudFront WAF), so
this curated list is the best available discovery path.
"""

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

from price_scraping.spiders._opencart_base import normalize_price

logger = logging.getLogger(__name__)

_BASE = "https://www.pacifiko.com"

CATEGORY_URLS = [
    f"{_BASE}/audifonos-deportivos",
    f"{_BASE}/audio-y-equipos-de-sonido",
    f"{_BASE}/cafeteras",
    f"{_BASE}/camaras-de-accion-y-accesorios",
    f"{_BASE}/celulares-y-smartphones-desbloqueados",
    f"{_BASE}/cuidado-del-cabello",
    f"{_BASE}/jbl",
    f"{_BASE}/kitchenaid",
    f"{_BASE}/laptops",
    f"{_BASE}/licuadoras",
    f"{_BASE}/maquinas-de-coser",
    f"{_BASE}/marshall",
    f"{_BASE}/monitores",
    f"{_BASE}/motorola",
    f"{_BASE}/nintendo-consolas",
    f"{_BASE}/relojes-inteligentes",
    f"{_BASE}/videojuegos",
    f"{_BASE}/xiaomi-tienda",
    f"{_BASE}/index.php?route=product/category&path=2267",  # Celulares y Accesorios
    f"{_BASE}/index.php?route=product/category&path=2604",  # Electrodomesticos
    f"{_BASE}/index.php?route=product/category&path=509581",  # Termos y Pachones
]
MAX_PAGES = 40

PRICE_SELECTORS = (
    "span.price-new::text",
    "span.price-special::text",
    "span.price::text",
)


class PacifikoGtSpider(scrapy.Spider):
    name = "pacifiko_gt"
    allowed_domains = ["pacifiko.com", "www.pacifiko.com"]
    currency = "GTQ"
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
        self.total_items = 0

    async def start(self):
        for url in CATEGORY_URLS:
            yield scrapy.Request(
                url, callback=self.parse_category, meta={"page": 1, "cat_url": url}
            )

    def parse_category(self, response):
        cards = response.css("div.product-layout")
        page = response.meta["page"]
        cat_url = response.meta["cat_url"]
        h1 = response.css("h1::text").get()
        category = h1.strip() if h1 else None
        n = 0
        for card in cards:
            item = self._item(card, response, category)
            if item:
                n += 1
                self.total_items += 1
                yield item
        logger.info(
            f"pacifiko_gt: {response.url} page={page} cards={len(cards)} items={n}"
        )

        if cards and page < MAX_PAGES:
            nxt = page + 1
            sep = "&" if "?" in cat_url else "?"
            yield scrapy.Request(
                f"{cat_url}{sep}page={nxt}",
                callback=self.parse_category,
                meta={"page": nxt, "cat_url": cat_url},
            )

    def _item(self, card, response, category):
        product_id = card.attrib.get("id")
        name = card.attrib.get("data-name")
        if not product_id or not name:
            return None
        name = re.sub(r"\s+", " ", name).strip()
        href = card.css("a.listing-product-link::attr(href)").get()
        price_text = None
        for sel in PRICE_SELECTORS:
            val = card.css(sel).get()
            if val and val.strip():
                price_text = val
                break
        price = normalize_price(price_text) if price_text else None
        if not price:
            return None
        return {
            "product_id": product_id,
            "product_name": name[:500],
            "category": category,
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": urljoin(response.url, href) if href else response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def closed(self, reason):
        if self.total_items == 0:
            logger.error(
                f"pacifiko_gt: crawl finished (reason={reason}) with ZERO items -- "
                "selectors likely stale, do not ship."
            )
