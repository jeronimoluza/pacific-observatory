"""
Spider for Gurkerl.at (Austria) -- https://www.gurkerl.at/.

Gurkerl is the Rohlik Group's Austrian online grocery delivery service
(sibling to rohlik_cz/CZ and kifli_hu/HU -- same Next.js storefront
family, different per-country category-id space). Unlike rohlik_cz, the
top-level category tree is not embedded in the homepage `__NEXT_DATA__`
payload and the header nav only exposes a handful of thematic/promo
sub-categories on a bare fetch (verified 2026-09-06) -- not the full
department list.

Instead this spider walks `sitemap_products.xml` (2.4MB, plain XML,
`ROBOTSTXT_OBEY: False` not even needed -- sitemap is unauthenticated and
un-blocked), which lists every product's canonical PDP URL in the form
`https://www.gurkerl.at/{productId}-{slug}`. Product ids are extracted
directly from the `<loc>` path (leading digits before the first `-`), then
batched through the same `/api/v1/products/card` endpoint rohlik_cz uses:

  GET /api/v1/products/card?products=<id>&products=<id>...&categoryType=normal
      -> [{"productId","name","slug","unit","textualAmount",
           "prices":{"originalPrice","salePrice","currency":"EUR"},...}]
      (100-id batch confirmed to work in one call, verified live 2026-09-06)

Confirmed live 2026-09-06: productId 972 "Heineken" EUR 1.79/500ml,
productId 1450 "Baileys Original Irish Cream Liqueur" EUR 17.99/0.7l --
both re-checked against the rendered PDP.

No category/breadcrumb is available from either the sitemap or the card
endpoint, so `category` is left null (the PDP itself is a client-rendered
SPA that would need a Playwright hit per product to recover it -- not
worth it against thousands of SKUs). PDP url is built directly from the
sitemap `<loc>`, not re-derived, since the API's `slug` field can omit
diacritics/variants the canonical URL keeps.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.gurkerl.at"
_SITEMAP_URL = f"{_BASE}/sitemap_products.xml"
_LOC_RE = re.compile(r"<loc>(https://www\.gurkerl\.at/(\d+)-[^<]+)</loc>")
CARD_BATCH = 100
MAX_PRODUCTS = 8000  # safety cap; full sitemap is larger


class GurkerlAtSpider(scrapy.Spider):
    name = "gurkerl_at"
    allowed_domains = ["gurkerl.at"]
    currency = "EUR"
    language = "de"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "DEFAULT_REQUEST_HEADERS": {"Referer": "https://www.gurkerl.at/"},
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def start_requests(self):
        yield scrapy.Request(_SITEMAP_URL, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        pairs = _LOC_RE.findall(response.text)
        logger.info(f"gurkerl_at: sitemap yielded {len(pairs)} product urls")
        pairs = pairs[:MAX_PRODUCTS]
        for i in range(0, len(pairs), CARD_BATCH):
            chunk = pairs[i : i + CARD_BATCH]
            ids = [pid for _, pid in chunk]
            url_by_id = {pid: url for url, pid in chunk}
            qs = "&".join(f"products={pid}" for pid in ids)
            yield scrapy.Request(
                f"{_BASE}/api/v1/products/card?{qs}&categoryType=normal",
                callback=self.parse_cards,
                meta={"url_by_id": url_by_id},
            )

    def parse_cards(self, response):
        url_by_id = response.meta["url_by_id"]
        try:
            cards = response.json()
        except ValueError:
            return
        scraped_at = datetime.now(timezone.utc).isoformat()
        for card in cards:
            if card.get("type") != "PRODUCT":
                continue
            pid = str(card.get("productId"))
            prices = card.get("prices") or {}
            price = prices.get("salePrice") or prices.get("originalPrice")
            name = (card.get("name") or "").strip()
            if not name or price is None or price <= 0:
                continue
            yield {
                "product_id": pid,
                "product_name": name[:500],
                "category": None,
                "price": price,
                "currency": prices.get("currency", self.currency),
                "available": True,
                "url": url_by_id.get(pid, f"{_BASE}/{pid}"),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
