"""
Spider for Kifli (Hungary) -- https://www.kifli.hu/.

Kifli is Rohlik Group's Hungarian online grocery brand (same group as
rohlik.cz/CZ, knuspr.de/DE, gurkerl.at/AT) and runs the IDENTICAL
Next.js platform and JSON API as rohlik_cz (confirmed live 2026-09-01 --
same /api/v1/categories/normal/{id}/products and /api/v1/products/card
paths, same /c{categoryId}/{slug} PDP scheme, just a different domain
and HUF currency). See rohlik_cz.py for the full API discovery notes;
not repeated here.

  GET /api/v1/categories/normal/{categoryId}/products
      ?page=<N>&size=100&sort=recommended&filter=
      -> {"productIds": [...]}
  GET /api/v1/products/card?products=<id>&...&categoryType=normal
      -> [{"productId","name","slug","prices":{"originalPrice",
           "salePrice","currency":"HUF"}}]
  PDP: /c{categoryId}/{slug} -- verified live, HTTP 200.

Top-level category ids harvested from the homepage nav (2026-09-01):
Marks & Spencer (packaged food range), shelf-stable, fruit & veg,
beverages, dairy & eggs, bakery & pastry, frozen food, meat & fish,
cold cuts & ready meals, beauty, chemical & paper goods, baby & child,
home & office, pet food & supplies, plant-based, grilling & BBQ,
ready meals & quick dishes -- a normal full-basket supermarket catalog,
food-and-beverage led. As with rohlik_cz, the same product_id can appear
under more than one of these (e.g. a plant-based item also filed under
dairy), so results are deduped by product_id within the crawl.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.kifli.hu"
_TOP_CATEGORY_IDS = [
    300113032,  # marks-spencer
    300113035,  # tartos-elelmiszer (shelf-stable)
    300113038,  # zoeldseg-es-gyuemoelcs (fruit & veg)
    300113062,  # italok (beverages)
    300113137,  # tejtermek-es-tojas (dairy & eggs)
    300113263,  # pekseg-es-cukraszat (bakery & pastry)
    300114559,  # fagyasztott-elelmiszer (frozen)
    300114760,  # hus-es-hal (meat & fish)
    300114817,  # felvagott-es-keszetel (cold cuts & ready meals)
    300114859,  # szepsegapolas (beauty)
    300115141,  # vegyi-es-papiraru (chemical & paper goods)
    300115258,  # baba-es-gyerek (baby & child)
    300115504,  # otthon-iroda (home & office)
    300115906,  # allateledel-felszereles (pet food & supplies)
    300121569,  # noevenyi-alapu (plant-based)
    300124226,  # grillezes-es-bbq (grilling & BBQ)
    300124706,  # keszetelek-es-gyors-fogasok (ready meals & quick dishes)
]
PAGE_SIZE = 100
MAX_PAGES = 60
CARD_BATCH = 100


class KifliHuSpider(scrapy.Spider):
    name = "kifli_hu"
    allowed_domains = ["kifli.hu"]
    currency = "HUF"
    language = "hu"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "DEFAULT_REQUEST_HEADERS": {"Referer": "https://www.kifli.hu/"},
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seen_ids = set()

    async def start(self):
        for cat_id in _TOP_CATEGORY_IDS:
            yield scrapy.Request(
                f"{_BASE}/api/v1/categories/normal/{cat_id}/products"
                f"?page=0&size={PAGE_SIZE}&sort=recommended&filter=",
                callback=self.parse_category_page,
                meta={"cat_id": cat_id, "page": 0},
            )

    def parse_category_page(self, response):
        cat_id = response.meta["cat_id"]
        page = response.meta["page"]
        try:
            data = response.json()
        except ValueError:
            return
        ids = data.get("productIds") or []
        logger.info(f"kifli_hu: cat={cat_id} page={page} ids={len(ids)}")
        for i in range(0, len(ids), CARD_BATCH):
            chunk = ids[i : i + CARD_BATCH]
            qs = "&".join(f"products={pid}" for pid in chunk)
            yield scrapy.Request(
                f"{_BASE}/api/v1/products/card?{qs}&categoryType=normal",
                callback=self.parse_cards,
                meta={"cat_id": cat_id},
            )
        if len(ids) == PAGE_SIZE and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{_BASE}/api/v1/categories/normal/{cat_id}/products"
                f"?page={nxt}&size={PAGE_SIZE}&sort=recommended&filter=",
                callback=self.parse_category_page,
                meta={"cat_id": cat_id, "page": nxt},
            )

    def parse_cards(self, response):
        cat_id = response.meta["cat_id"]
        try:
            cards = response.json()
        except ValueError:
            return
        scraped_at = datetime.now(timezone.utc).isoformat()
        for card in cards:
            if card.get("type") != "PRODUCT":
                continue
            pid = card["productId"]
            if pid in self._seen_ids:
                continue
            prices = card.get("prices") or {}
            price = prices.get("salePrice") or prices.get("originalPrice")
            if price is None or price <= 0:
                continue
            self._seen_ids.add(pid)
            slug = card.get("slug") or ""
            yield {
                "product_id": pid,
                "product_name": (card.get("name") or "").strip()[:500],
                "category": str(cat_id),
                "price": price,
                "currency": prices.get("currency", self.currency),
                "available": True,
                "url": f"{_BASE}/c{cat_id}/{slug}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
