"""
Spider for Yorix (Cameroon) — https://www.yorix.cm/.

Custom React/Vite SPA backed by a public Supabase project. The `products`
table is exposed via the standard Supabase PostgREST API and readable with
just the publishable anon key (captured from live request headers, no auth
flow needed):

GET https://msrymchhhxitdevthvdi.supabase.co/rest/v1/products
    ?select=id,name_fr,prix,categorie&limit=1000&offset=N
Header: apikey: sb_publishable_yJj7JNdn-r19Pjc070IOBg_y2VzGJXA

Re-verified live 2026-08-06: HTTP 200, 189 total products in one page
(limit=1000 covers the whole table today; offset pagination kept as a
safety net for growth). Sample: 'sac de luxe au cameroun' 60000 XAF.
Currency confirmed XAF (matches countries.yaml; whole-number FCFA amounts,
no minor units). General classifieds-style marketplace, not food-specific —
walked whole-catalog per instructions; the classifier sorts COICOP leaves
downstream (categories seen: Alimentation, Produits frais, Cosmetiques,
Mode, Telephones, Automobile, etc.).
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://msrymchhhxitdevthvdi.supabase.co/rest/v1/products"
_APIKEY = "sb_publishable_yJj7JNdn-r19Pjc070IOBg_y2VzGJXA"
_PAGE_SIZE = 1000
_MAX_PAGES = 50  # safety cap


class YorixCmSpider(scrapy.Spider):
    name = "yorix_cm"
    allowed_domains = ["msrymchhhxitdevthvdi.supabase.co"]
    currency = "XAF"
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
        yield self._request(offset=0)

    def _request(self, offset: int) -> scrapy.Request:
        url = (
            f"{_BASE}?select=id,name_fr,prix,categorie"
            f"&limit={_PAGE_SIZE}&offset={offset}"
        )
        return scrapy.Request(
            url,
            headers={"apikey": _APIKEY},
            callback=self.parse_page,
            meta={"offset": offset},
        )

    def parse_page(self, response):
        try:
            products = response.json()
        except ValueError:
            logger.warning(f"non-JSON response at {response.url}")
            return
        if not isinstance(products, list) or not products:
            return
        offset = response.meta["offset"]
        logger.info(f"yorix_cm offset={offset} count={len(products)}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in products:
            price = p.get("prix")
            if price is None:
                continue
            yield {
                "product_id": str(p.get("id")),
                "product_name": str(p.get("name_fr") or "").strip()[:500],
                "category": p.get("categorie"),
                "price": str(price),
                "currency": self.currency,
                "available": True,
                "url": f"https://www.yorix.cm/#{p.get('id')}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        page = offset // _PAGE_SIZE
        if len(products) >= _PAGE_SIZE and page < _MAX_PAGES:
            yield self._request(offset=offset + _PAGE_SIZE)
