"""Yandex Lavka Russia -- https://lavka.yandex.ru/ (Moscow).

Yandex Lavka is Russia's largest quick-commerce grocery (dark-store
delivery). The Russia inventory parked it as "homepage embeds a React-Query
state dump with a Moscow default geolocation and category tiles, but no
product-level price data in that dump; the real catalog API was not
reverse-engineered this wave". It does not need reverse-engineering: it is
the SAME white-label Lavka platform already onboarded as ``lavka_uz``
(lavka.yandex.uz) and ``globus_online_kg`` (globus-online.kg), so the
existing three-POST unlock applies verbatim with a Russian point and RUB.

Flow (no auth, no cookies to carry by hand, no TLS impersonation):

1. GET ``/`` -> ``csrfToken`` out of the ``<script id="__page_props__-data">``
   blob (and a ``lavka__session`` cookie via Set-Cookie).
2. POST ``/api/v1/providers/geo/v1/geocode`` with a fixed Moscow point
   (Red Square 3, 55.7539/37.6208) -> ``{city, street, house, buildingId}``;
   ``buildingId`` is the ``geoId`` every catalog call needs.
3. POST ``/api/v1/providers/v1/layout`` (``layoutSlug: "grocery"``) -> the
   live category tree for the depot serving that point. Verified 2026-09-05:
   74 categories (Молочное и яйца, Мясо и птица, Рыба, Фрукты и овощи,
   Бакалея, Напитки, Хлеб, Замороженное, Готовая еда, «Из Лавки» own-label,
   Аптека, Зоотовары, ...).
4. POST ``/api/v1/providers/v2/category`` once per category id -> a flat,
   server-deduplicated ``products`` array for the whole branch (1,034
   products in the first category alone).

Unlike ``lavka_uz``, the categories on the Russian layout carry BOTH a
``categoryInfo.id`` hash and a ``deepLink`` slug; the ``id`` is what is sent
as ``categoryId`` here (verified live), while the ``deepLink`` is used only
to build a human-meaningful Referer and product URL.

The catalog is address-pinned -- a different address can resolve to a
different depot and assortment -- so one fixed, real central-Moscow point is
pinned for reproducibility, matching the single-city convention used by the
other Russian sources.

Product detail is a client-side modal, not a route, so ``url`` is synthesized
as the owning category page plus a ``#<product_id>`` fragment (the
``lavka_uz``/``globus_online_kg`` precedent, and what keeps
DuplicationPipeline's url-dedup from collapsing distinct products).
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://lavka.yandex.ru"
_BOOTSTRAP_URL = f"{_BASE}/"
# Red Square 3, central Moscow -- a real, serviceable point pinned so the
# depot/assortment is reproducible across runs.
_POINT = {"lon": 37.6208, "lat": 55.7539}
_PAGE_PROPS_RE = re.compile(r'<script id="__page_props__-data"[^>]*>(.*?)</script>', re.S)
_SOFT_HYPHEN = "­"
_CURRENCY_SIGN = "₽"


def _headers(csrf: str, referer: str) -> dict:
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "X-Csrf-Token": csrf,
        "X-Csrf-Token-Bff": csrf,
        "X-Lavka-Web-Locale": "ru-RU",
        "X-Lavka-Web-City": "213",  # Moscow
        "Referer": referer,
    }


class LavkaRuSpider(scrapy.Spider):
    name = "lavka_ru"
    allowed_domains = ["lavka.yandex.ru"]
    currency = "RUB"
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
            logger.warning("%s: no __page_props__-data at %s", self.name, response.url)
            return
        try:
            csrf = json.loads(m.group(1))["csrfToken"]
        except (ValueError, KeyError):
            logger.warning("%s: could not read csrfToken", self.name)
            return
        yield scrapy.Request(
            f"{_BASE}/api/v1/providers/geo/v1/geocode",
            method="POST",
            headers=_headers(csrf, _BOOTSTRAP_URL),
            body=json.dumps(
                {
                    "point": _POINT,
                    "lang": "ru",
                    "suppressError": True,
                    "action": "pin_drop",
                }
            ),
            callback=self.parse_geocode,
            meta={"csrf": csrf},
        )

    def parse_geocode(self, response):
        try:
            geo = response.json()
        except ValueError:
            logger.warning("%s: bad geocode response", self.name)
            return
        csrf = response.meta["csrf"]
        yield scrapy.Request(
            f"{_BASE}/api/v1/providers/v1/layout",
            method="POST",
            headers=_headers(csrf, _BOOTSTRAP_URL),
            body=json.dumps(self._payload(geo, {"layoutSlug": "grocery"})),
            callback=self.parse_layout,
            meta={"csrf": csrf, "geo": geo},
        )

    @staticmethod
    def _payload(geo, extra):
        payload = {
            "modes": ["grocery"],
            "position": {"location": [geo["lon"], geo["lat"]]},
            "additionalData": {
                "city": geo.get("city"),
                "street": geo.get("street"),
                "house": geo.get("house"),
            },
            "geoId": geo.get("buildingId"),
            "currencySign": _CURRENCY_SIGN,
            "depotType": "regular",
        }
        payload.update(extra)
        return payload

    def parse_layout(self, response):
        try:
            data = response.json()
        except ValueError:
            logger.warning("%s: bad layout response", self.name)
            return
        csrf = response.meta["csrf"]
        geo = response.meta["geo"]

        cats, seen = [], set()
        for section in data.get("sections") or []:
            for cat in section.get("categories") or []:
                info = cat.get("categoryInfo") or {}
                if info.get("type") and info.get("type") != "category":
                    continue
                cid = info.get("id")
                if cid and cid not in seen:
                    seen.add(cid)
                    label = (
                        cat.get("title")
                        or info.get("title")
                        or info.get("deepLink")
                        or cid
                    )
                    cats.append((cid, info.get("deepLink") or cid, label))
        logger.info("%s: %d categories", self.name, len(cats))

        for cid, slug, label in cats:
            referer = f"{_BASE}/catalog/grocery/category/{slug}"
            yield scrapy.Request(
                f"{_BASE}/api/v1/providers/v2/category",
                method="POST",
                headers=_headers(csrf, referer),
                body=json.dumps(
                    self._payload(
                        geo,
                        {
                            "categoryId": cid,
                            "categorySlugPath": {"layoutSlug": "grocery"},
                        },
                    )
                ),
                callback=self.parse_category,
                meta={"slug": slug, "label": label},
                dont_filter=True,
            )

    def parse_category(self, response):
        slug = response.meta["slug"]
        label = response.meta.get("label") or slug
        try:
            data = response.json()
        except ValueError:
            logger.warning("%s: bad category response for %s", self.name, slug)
            return
        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in data.get("products") or []:
            if p.get("type") != "good":
                continue
            pid = p.get("id")
            price = p.get("currentPrice")
            if price in (None, ""):
                price = p.get("price")
            name = (
                (p.get("longTitle") or p.get("title") or "")
                .replace(_SOFT_HYPHEN, "")
                .strip()
            )
            if not pid or not name or price in (None, ""):
                continue
            try:
                amount = float(str(price).replace(" ", "").replace(" ", "").replace(",", "."))
            except ValueError:
                continue
            if amount <= 0:
                continue
            yield {
                "product_id": str(pid),
                "product_name": name[:500],
                "category": label,
                "price": f"{amount:.2f}",
                "currency": self.currency,
                "available": bool(p.get("available", False)),
                "url": f"{_BASE}/catalog/grocery/category/{slug}#{pid}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
