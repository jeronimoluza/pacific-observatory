"""
Spider for Rohlik (Czech Republic) -- https://www.rohlik.cz/.

Rohlik is Czechia's largest online-only grocery delivery service (Rohlik
Group also runs Knuspr/DE, Gurkerl/AT, Kifli/HU -- Slovakia is not
covered by the group). The storefront is a Next.js SPA. Category listing
pages embed a `__NEXT_DATA__` React-Query cache, but appending `?page=N`
to the category URL does NOT change it (re-verified 2026-09-01: page=0
and page=1 embed the exact same 28 `productCardInfo` ids -- a prior
version of this spider assumed cumulative SSR growth here and was wrong;
do not reintroduce that approach). Real pagination lives behind a
client-side API found via a Playwright network trace, which needs no
auth and no session cookie:

  GET /api/v1/categories/normal/{categoryId}/products
      ?page=<N>&size=100&sort=recommended&filter=
      -> {"productIds": [...]}  (size=100 confirmed to work, cuts request
      count vs. the site's own default size=14; page N really does return
      a disjoint id set from page N-1 -- verified against page=0/page=1)

  GET /api/v1/products/card?products=<id>&products=<id>...&categoryType=normal
      -> [{"productId", "name", "unit", "textualAmount",
           "prices": {"originalPrice", "salePrice", "currency": "CZK"}}]
      (confirmed to accept a 100-id batch in one call; response carries no
      category or slug-path field, only the bare product slug)

Canonical PDP url is /c{categoryId}/{slug} (verified live, 200, both with
the top-level walked category id and a product's own subcategory id --
/{slug}, /detail/{slug}, and /p/{slug}-{id} all 404).

Top-level category ids harvested from the homepage nav (2026-09-01):
bakery, fruit/veg, meat/fish, deli, dairy/chilled, shelf-stable, frozen,
beverages, drugstore, baby, household/garden, pet, special nutrition,
grilling, plant-based, cosmetics, ready-meals -- a normal full-basket
supermarket catalog, food-and-beverage led.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.rohlik.cz"
_TOP_CATEGORY_IDS = [
    300101000,  # pekarna-a-cukrarna (bakery)
    300102000,  # ovoce-a-zelenina (fruit & veg)
    300103000,  # maso-a-ryby (meat & fish)
    300104000,  # uzeniny-a-lahudky (cold cuts & deli)
    300105000,  # mlecne-a-chlazene (dairy & chilled)
    300106000,  # trvanlive (shelf-stable)
    300107000,  # mrazene (frozen)
    300108000,  # napoje (beverages)
    300109000,  # drogerie (drugstore)
    300110000,  # dite (baby)
    300111000,  # domacnost-a-zahrada (household & garden)
    300112000,  # zvire (pet)
    300112393,  # specialni-vyziva (special nutrition)
    300117503,  # grilovani (grilling)
    300121429,  # plant-based
    300124206,  # kosmetika (cosmetics)
    300124876,  # mame-navareno (ready meals)
]
# NOTE: the thematic-looking ids (specialni-vyziva, grilovani, plant-based,
# mame-navareno) look like cross-cuts of the "real" departments but are
# NOT redundant -- verified live 2026-09-01 against a full run: of 10,395
# distinct product_ids, 3,177 exist ONLY inside these four categories
# (e.g. oat/almond "barista" milk alternatives are never cross-listed
# under mlecne-a-chlazene). Dropping them would silently lose ~30% of the
# catalog's distinct SKUs. The real duplication (~3,200 rows where the
# same product_id is emitted under two categories, e.g. an item that is
# both dairy and plant-based) is handled by the in-spider `_seen` dedup
# below instead.
PAGE_SIZE = 100
MAX_PAGES = 60  # safety cap per category (60 * 100 = 6,000 SKUs/category)
CARD_BATCH = 100


class RohlikCzSpider(scrapy.Spider):
    name = "rohlik_cz"
    allowed_domains = ["rohlik.cz"]
    currency = "CZK"
    language = "cs"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "DEFAULT_REQUEST_HEADERS": {"Referer": "https://www.rohlik.cz/"},
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
        logger.info(f"rohlik_cz: cat={cat_id} page={page} ids={len(ids)}")
        for i in range(0, len(ids), CARD_BATCH):
            chunk = ids[i : i + CARD_BATCH]
            qs = "&".join(f"products={pid}" for pid in chunk)
            yield scrapy.Request(
                f"{_BASE}/api/v1/products/card?{qs}&categoryType=normal",
                callback=self.parse_cards,
                meta={"cat_id": cat_id},
            )
        # `>=`, not `==`: the API answers `size=100` with **101** productIds on
        # some categories and exactly 100 on others. An equality test therefore
        # stopped 7 of 17 categories dead after page 0 -- measured 2026-09-01,
        # e.g. specialni-vyziva (300112393) returned 101 ids and was truncated
        # to a single page, silently losing 754 distinct products. Because the
        # sort is `recommended` (a rotating order), a different set of
        # categories truncated on each run, so successive runs disagreed by
        # ~800 products and no single run was complete.
        if len(ids) >= PAGE_SIZE and page < MAX_PAGES:
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
                "product_id": card["productId"],
                "product_name": (card.get("name") or "").strip()[:500],
                "category": str(cat_id),
                "price": price,
                "currency": prices.get("currency", self.currency),
                "available": True,
                "url": f"{_BASE}/c{cat_id}/{slug}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
