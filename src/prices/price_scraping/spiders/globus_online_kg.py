"""Spider for Globus Online -- https://globus-online.kg/ (Bishkek, Kyrgyz Republic).

NOTE: this is unrelated to globus.ru (the Russian hypermarket chain, which
times out from this network -- see known_blockers.md). "Globus Online" here
is a rapid-grocery-delivery storefront run on Yandex's white-label Lavka
platform ("grocery-b2b-website" / "lavkaweb", merchant name "umai" / "ОсОО
Умай Групп") -- the exact same client-rendered React app + JSON API shape as
the sibling `lavka_uz` spider (lavka.yandex.uz), just deployed under its own
domain and branding, on a "b2b" host flavor
(`pageEnv.application.lavkaHost == "b2b"`, `merchant.isB2b == true`).

Confirmed via the raw `__page_props__-data` JSON blob on any category page:
`pageEnv.hostname == "globus-online.kg"`, `pageEnv.locale.region == "KG"`,
`pageEnv.cityId == 10309` (Bishkek). No TLS fingerprinting or curl_cffi
needed -- plain `requests`/Scrapy UA works throughout.

Flow (identical shape to lavka_uz, different category-tree schema):

1. GET any `/ru-kg/catalog/grocery/category/<id>` page (or the homepage) --
   pulls a session cookie (`lavka__session`, `yandexuid`, ...) via Set-Cookie
   and a `csrfToken` out of `<script id="__page_props__-data">`.
2. POST `/api/v1/providers/geo/v1/geocode` with a fixed Bishkek point (Ala-Too
   Square, 42.87455/74.59697) -> {city, street, house, buildingId}.
   `buildingId` doubles as the `geoId` every catalog call needs.
3. POST `/api/v1/providers/v1/layout` (layoutSlug=grocery) -> returns 19
   section groups (Бакалея, Вода и напитки, Овощной прилавок, Алкогольные
   напитки, Сладкое и снеки, Хлебобулочная, Мясная лавка, Молочный прилавок,
   Замороженные продукты, Красота и гигиена, Стирка и уборка, Товары для
   животных, Дом и Уют, ...). Unlike lavka_uz, leaf categories here carry a
   `categoryInfo.id` hash (no `deepLink` slug) -- 73 distinct leaf category
   ids, filtered to `categoryInfo.type == "category"` (skipping the
   `category_group` header entries).
4. POST `/api/v1/providers/v2/category` once per leaf category id (position
   + geoId, `categoryId: <id>`, `categorySlugPath: {layoutSlug: "grocery"}`)
   -> returns a flat `products` array for that category (612 products seen
   for "Крупы и макароны" alone -- not a per-subcategory walk).

Verified live 2026-09-01: depot region KG/Bishkek, currency KGS ("сом").
Sample real SKUs: 'Макароны Алтайская сказка рожки 5кг' 450 KGS, 'Макароны
Barilla Bucatini №9 400г' 181 KGS, 'Перловка вес Кампа азык' (bulk pearl
barley). Titles occasionally carry Unicode soft hyphens (U+00AD, seen in the
`title` field but not `longTitle`) -- stripped defensively here regardless
of which field is used.

The site serves both a ru-KG and ky-KG locale (`meta.common.alternates` on
every page lists both hreflang variants) -- rule 21 territory. This spider
sidesteps the duplicate-catalog trap structurally rather than by
post-hoc dedup: it sends `X-Lavka-Web-Locale: ru-KG` on every request and
walks the category tree exactly once, so no ky-KG rows are ever fetched.

The catalog is address-pinned (a different address can resolve to a
different depot/assortment); this spider pins one fixed, real Bishkek point
so results are reproducible across runs. Beauty/hygiene, cleaning, and pet
categories are non-food but are walked too since they are part of the same
live depot assortment -- channel is `supermarket` (rapid grocery delivery),
matching `lavka_uz`.

No canonical per-product URL exists (product detail is a client-side modal,
not a route); `url` is synthesized as the owning category page plus a
`#<product_id>` fragment, per the DuplicationPipeline url-dedup trap.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://globus-online.kg"
_BOOTSTRAP_URL = (
    f"{_BASE}/ru-kg/catalog/grocery/category/01fbaadb89bd11d53b0f182fe565fa91"
)
# Ala-Too Square, central Bishkek -- a real, serviceable point used to pin a
# reproducible depot/assortment across runs.
_POINT = {"lon": 74.59697, "lat": 42.87455}
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
        "X-Lavka-Web-Locale": "ru-KG",
        "Referer": referer,
    }


class GlobusOnlineKgSpider(scrapy.Spider):
    name = "globus_online_kg"
    allowed_domains = ["globus-online.kg"]
    currency = "KGS"
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
            logger.warning(
                "globus_online_kg: no __page_props__-data at %s", response.url
            )
            return
        try:
            csrf = json.loads(m.group(1))["csrfToken"]
        except (ValueError, KeyError):
            logger.warning("globus_online_kg: could not read csrfToken")
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
            logger.warning("globus_online_kg: bad geocode response")
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
            "currencySign": "сом",
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
            logger.warning("globus_online_kg: bad layout response")
            return
        csrf = response.meta["csrf"]
        geo = response.meta["geo"]
        cat_ids: list[str] = []
        seen: set[str] = set()
        for section in data.get("sections") or []:
            for cat in section.get("categories") or []:
                info = cat.get("categoryInfo") or {}
                if info.get("type") != "category":
                    continue
                cid = info.get("id")
                if cid and cid not in seen:
                    seen.add(cid)
                    cat_ids.append(cid)
        logger.info("globus_online_kg: %d leaf categories", len(cat_ids))
        for cid in cat_ids:
            referer = f"{_BASE}/ru-kg/catalog/grocery/category/{cid}"
            cat_payload = {
                "modes": ["grocery"],
                "categoryId": cid,
                "categorySlugPath": {"layoutSlug": "grocery"},
                "position": {"location": [geo["lon"], geo["lat"]]},
                "additionalData": {
                    "city": geo["city"],
                    "street": geo["street"],
                    "house": geo["house"],
                },
                "geoId": geo["buildingId"],
                "currencySign": "сом",
                "depotType": "regular",
            }
            yield scrapy.Request(
                f"{_BASE}/api/v1/providers/v2/category",
                method="POST",
                headers=_headers(csrf, referer),
                body=json.dumps(cat_payload),
                callback=self.parse_category,
                meta={"category_id": cid},
            )

    def parse_category(self, response):
        cid = response.meta["category_id"]
        try:
            data = response.json()
        except ValueError:
            logger.warning("globus_online_kg: bad category response for %s", cid)
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
            name = re.sub(r"\s+", " ", name)
            if not pid or not name or price is None:
                continue
            yield {
                "product_id": str(pid),
                "product_name": name[:500],
                "category": cid,
                "price": str(price),
                "currency": self.currency,
                "available": bool(p.get("available", False)),
                "url": f"{_BASE}/ru-kg/catalog/grocery/category/{cid}#{pid}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
