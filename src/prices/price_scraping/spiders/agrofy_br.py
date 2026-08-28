"""
Spider for Agrofy Brasil (Brazil) -- https://www.agrofy.com.br/.

Used farm-machinery classifieds marketplace (React/Next.js SSR, Microsoft-IIS),
not a food or standardized-retail source: listings are individually-priced
used tractors, combine harvesters, seeders, sprayers, etc. Each category page
embeds a `__NEXT_DATA__` JSON blob with `props.pageProps.listing.Hits`, a
clean array of listing dicts (id/name/price/currency/url/category), so this
is a JSON-in-HTML parse rather than a CSS-selector scrape. Real-estate
("Imoveis") and services/financing categories are excluded -- only the
machinery/equipment nav categories are crawled, per the marketplace's own
top-nav taxonomy.

Pagination is `?p=N` (NOT `?page=` or `?pagina=`, both of which silently
return page 1 again -- verified live 2026-08-17 by comparing first-item ids
across all three params).

Re-verified live 2026-08-17: GET /colheitadeiras -> 200, Hits[0] =
"Colheitadeira New Holland TC55 ano 1995", price 120000, currency "R$".
Currency is uniformly "R$" (BRL) across all sampled categories.
"""

import json
import logging
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.agrofy.com.br"
_CATEGORIES = [
    "tratores",
    "tratores-usados",
    "colheitadeiras",
    "semeadoras",
    "pulverizadores-agricolas",
    "grades-agricolas",
    "plataformas-agricolas",
    "enfardadeiras",
    "carretas-agricolas",
    "picadores-forrageiros",
    "distribuidores-de-fertilizantes",
]
MAX_PAGES_PER_CATEGORY = 20


class AgrofyBrSpider(scrapy.Spider):
    name = "agrofy_br"
    allowed_domains = ["agrofy.com.br"]
    currency = "BRL"
    language = "pt"

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
        self.seen_ids = set()
        for slug in _CATEGORIES:
            yield scrapy.Request(
                f"{_BASE}/{slug}",
                callback=self.parse_category,
                meta={"slug": slug, "page": 1},
            )

    def parse_category(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]
        raw = response.css("script#__NEXT_DATA__::text").get()
        if not raw:
            logger.warning(f"{self.name}: no __NEXT_DATA__ at {response.url}")
            return
        try:
            data = json.loads(raw)["props"]["pageProps"]
        except (json.JSONDecodeError, KeyError):
            logger.warning(f"{self.name}: malformed __NEXT_DATA__ at {response.url}")
            return
        hits = data.get("listing", {}).get("Hits") or []
        for hit in hits:
            item_id = hit.get("id")
            name = (hit.get("name") or "").strip()
            price = hit.get("price")
            url = hit.get("url")
            if item_id is None or not name or price is None or not url:
                continue
            if item_id in self.seen_ids:
                continue
            self.seen_ids.add(item_id)
            yield {
                "product_id": str(item_id),
                "product_name": name[:500],
                "category": hit.get("categoryName") or slug,
                "price": str(price),
                "currency": self.currency,
                "available": True,
                "url": urljoin(_BASE, url),
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        if hits and page < MAX_PAGES_PER_CATEGORY:
            yield scrapy.Request(
                f"{_BASE}/{slug}?p={page + 1}",
                callback=self.parse_category,
                meta={"slug": slug, "page": page + 1},
            )
