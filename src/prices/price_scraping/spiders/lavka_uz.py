"""Spider for Yandex Lavka grocery delivery -- https://lavka.yandex.uz/ (Tashkent, Uzbekistan).

lavka.yandex.uz is a client-rendered React app ("lavka-grocery-frontend-
standalone"). Loaded with no delivery address it serves a fake, hard-coded
"demo catalog" (literal on-page text: "Это демо-каталог. Укажите адрес,
чтобы посмотреть настоящий" -- "This is a demo catalog, enter an address to
see the real one") -- confirmed by inspecting the raw `__react_query_state__`
blob, whose `CatalogCategory` query resolves to a bare random float, not
product data. This is a genuine anti-scraping gate, not a JS-hydration
problem, so it is NOT reachable by simply reading the SSR HTML.

Reverse-engineered with a one-time Playwright network trace (discovery only
-- this spider itself makes plain `requests`/Scrapy calls, no browser at
collection time): once an address is confirmed, three plain JSON POSTs
unlock the real catalog with NO auth and NO TLS fingerprinting required
(plain `requests`/Scrapy UA works, no curl_cffi needed):

1. GET any `/catalog/grocery/category/<slug>` page -> pulls a session cookie
   (`lavka__session`, `yandexuid`, ...) via Set-Cookie and a `csrfToken` out
   of the `<script id="__page_props__-data">` JSON blob.
2. POST `/api/v1/providers/geo/v1/geocode` with a fixed lat/lon in central
   Tashkent (Salar embankment, 41.3279/69.3137) -> returns
   {city, street, house, buildingId, lat, lon}. `buildingId` doubles as the
   `geoId` every subsequent catalog call requires.
3. POST `/api/v1/providers/v1/layout` with `layoutSlug: "grocery"` and the
   geocoded position/geoId -> returns the live top-level category tree for
   the depot assigned to that point (21 categories: izlavki own-label,
   bakery, drinks, meat_and_poultry, fish_and_seafood, freezing, desserts,
   kidsnutrition, forcats (pet), home_cosmetics, pharmacy, ...).
4. POST `/api/v1/providers/v2/category` once per category slug (same
   position/geoId, plus `categoryId` and `categorySlugPath.layoutSlug`) ->
   returns a flat, already-deduplicated `products` array for that whole
   branch (subcategories are pre-merged server-side; no per-subcategory
   walk needed). No `cartId` is required -- cart fields on the request can
   be omitted entirely and the endpoint still returns full real pricing.

Verified live 2026-08-31: depot 2025010903, Tashkent, currency UZS
("currencySign": "сум"). Sample real SKUs: 'Стейк Рибай Black Angus' 299 990
UZS, 'Филе бедра цыплёнка-бройлера Joja' 42 990 UZS, 'Блины без начинки
«Из Лавки»' 30 990 UZS. Titles carry Unicode soft hyphens (U+00AD) inserted
for line-wrap hints in the app -- stripped here.

The catalog is address-pinned (a different address can resolve to a
different depot/assortment); this spider pins one fixed, real Tashkent
point so results are reproducible across runs. `pharmacy`/`home_cosmetics`/
`forcats` categories are non-food but are walked too since they are part of
the same live depot assortment -- channel is `supermarket` (rapid grocery
delivery), matching the sibling `korzinka_uz`/`makromarket_uz` sources.

No canonical per-product URL exists (product detail is a client-side modal,
not a route -- `/product/<deepLink>` 404s); `url` is synthesized as the
owning category page plus a `#<product_id>` fragment, per the
DuplicationPipeline url-dedup trap (fragments are unique per product id and
the base path always resolves 200).
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://lavka.yandex.uz"
_BOOTSTRAP_URL = f"{_BASE}/catalog/grocery/category/izlavki"
# Central Tashkent (Salar embankment) -- a real, serviceable point used to
# pin a reproducible depot/assortment across runs.
_POINT = {"lon": 69.31371087861851, "lat": 41.32789883113314}
_PAGE_PROPS_RE = re.compile(
    r'<script id="__page_props__-data"[^>]*>(.*?)</script>', re.S
)
_SOFT_HYPHEN = "­"


def _headers(csrf: str, referer: str) -> dict:
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "X-Csrf-Token": csrf,
        "X-Csrf-Token-Bff": csrf,
        "X-Lavka-Web-Locale": "ru-RU",
        "X-Lavka-Web-City": "213",
        "Referer": referer,
    }


class LavkaUzSpider(scrapy.Spider):
    name = "lavka_uz"
    allowed_domains = ["lavka.yandex.uz"]
    currency = "UZS"
    language = "ru"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(_BOOTSTRAP_URL, callback=self.parse_bootstrap)

    def parse_bootstrap(self, response):
        m = _PAGE_PROPS_RE.search(response.text)
        if not m:
            logger.warning("lavka_uz: no __page_props__-data at %s", response.url)
            return
        try:
            csrf = json.loads(m.group(1))["csrfToken"]
        except (ValueError, KeyError):
            logger.warning("lavka_uz: could not read csrfToken")
            return
        geo_payload = {
            "point": _POINT,
            "lang": "ru",
            "suppressError": True,
            "action": "pin_drop",
        }
        yield scrapy.Request(
            f"{_BASE}/api/v1/providers/geo/v1/geocode",
            method="POST",
            headers=_headers(csrf, _BOOTSTRAP_URL),
            body=json.dumps(geo_payload),
            callback=self.parse_geocode,
            meta={"csrf": csrf},
        )

    def parse_geocode(self, response):
        try:
            geo = response.json()
        except ValueError:
            logger.warning("lavka_uz: bad geocode response")
            return
        csrf = response.meta["csrf"]
        layout_payload = {
            "modes": ["grocery"],
            "layoutSlug": "grocery",
            "position": {"location": [geo["lon"], geo["lat"]]},
            "additionalData": {
                "city": geo["city"],
                "street": geo["street"],
                "house": geo["house"],
            },
            "geoId": geo["buildingId"],
            "currencySign": "сум",
            "depotType": "regular",
        }
        yield scrapy.Request(
            f"{_BASE}/api/v1/providers/v1/layout",
            method="POST",
            headers=_headers(csrf, _BOOTSTRAP_URL),
            body=json.dumps(layout_payload),
            callback=self.parse_layout,
            meta={"csrf": csrf, "geo": geo},
        )

    def parse_layout(self, response):
        try:
            data = response.json()
        except ValueError:
            logger.warning("lavka_uz: bad layout response")
            return
        csrf = response.meta["csrf"]
        geo = response.meta["geo"]
        slugs: list[str] = []
        seen: set[str] = set()
        for section in data.get("sections") or []:
            for cat in section.get("categories") or []:
                slug = (cat.get("categoryInfo") or {}).get("deepLink")
                if slug and slug not in seen:
                    seen.add(slug)
                    slugs.append(slug)
        logger.info("lavka_uz: %d top-level categories", len(slugs))
        for slug in slugs:
            referer = f"{_BASE}/catalog/grocery/category/{slug}"
            cat_payload = {
                "modes": ["grocery"],
                "categoryId": slug,
                "categorySlugPath": {"layoutSlug": "grocery"},
                "position": {"location": [geo["lon"], geo["lat"]]},
                "additionalData": {
                    "city": geo["city"],
                    "street": geo["street"],
                    "house": geo["house"],
                },
                "geoId": geo["buildingId"],
                "currencySign": "сум",
                "depotType": "regular",
            }
            yield scrapy.Request(
                f"{_BASE}/api/v1/providers/v2/category",
                method="POST",
                headers=_headers(csrf, referer),
                body=json.dumps(cat_payload),
                callback=self.parse_category,
                meta={"category_slug": slug},
            )

    def parse_category(self, response):
        slug = response.meta["category_slug"]
        try:
            data = response.json()
        except ValueError:
            logger.warning("lavka_uz: bad category response for %s", slug)
            return
        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in data.get("products") or []:
            if p.get("type") != "good":
                continue
            pid = p.get("id")
            price = p.get("currentPrice")
            name = (
                (p.get("longTitle") or p.get("title") or "")
                .replace(_SOFT_HYPHEN, "")
                .strip()
            )
            if not pid or not name or price is None:
                continue
            yield {
                "product_id": str(pid),
                "product_name": name[:500],
                "category": slug,
                "price": str(price),
                "currency": self.currency,
                "available": bool(p.get("available", False)),
                "url": f"{_BASE}/catalog/grocery/category/{slug}#{pid}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
