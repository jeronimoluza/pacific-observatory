"""
Spider for NolMarket (Benin) — https://nolmarket.com/.

React SPA (CRA, div#root) with a fully open Laravel JSON API at
/api/products?page=N — no auth needed, paginated 24/page. A live probe
confirmed total_pages=121, total=2887. Full-line catalog: Boissons,
Epicerie, Produits Frais (meat/fish/eggs, dairy, bakery), and a dedicated
Produits Locaux section (local grains/flour/oil forms).
"""

import html
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://nolmarket.com/api/products"
MAX_PAGES = 130


class NolmarketBjSpider(scrapy.Spider):
    name = "nolmarket_bj"
    allowed_domains = ["nolmarket.com"]
    currency = "XOF"
    language = "fr"

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
            f"{_BASE}?page=1",
            callback=self.parse_page,
            meta={"page": 1},
        )

    def parse_page(self, response):
        page = response.meta["page"]
        try:
            payload = response.json()
        except ValueError:
            logger.warning(f"nolmarket_bj: non-JSON response at page={page}")
            return
        products = payload.get("data") or []
        total_pages = payload.get("total_pages")
        logger.info(f"nolmarket_bj page={page}/{total_pages} count={len(products)}")
        if not products:
            return
        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in products:
            cat_parts = [c for c in (p.get("category"), p.get("sous_category")) if c]
            yield {
                "product_id": str(p.get("id")),
                "product_name": html.unescape(str(p.get("name") or "")).strip()[:500],
                "category": " > ".join(cat_parts) if cat_parts else None,
                "price": p.get("price"),
                "currency": self.currency,
                "available": (p.get("disponibility") or "").strip().lower() == "oui",
                "url": f"https://nolmarket.com/#{p.get('id')}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        if total_pages and page < min(total_pages, MAX_PAGES):
            nxt = page + 1
            yield scrapy.Request(
                f"{_BASE}?page={nxt}",
                callback=self.parse_page,
                meta={"page": nxt},
            )
