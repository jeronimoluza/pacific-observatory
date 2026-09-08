"""
Spider for OLX Ukraine (www.olx.ua) -- consumer-goods classifieds.

Same OLX Group platform and frontend generation as olx.ro/olx.pl/olx.ba:
category listing pages are React SSR and embed the full result set as a
JSON-in-JS-string blob, `window.__PRERENDERED_STATE__= "<escaped JSON>"`, at
`listing.listing.ads[]`. The string is JS-escaped, so it is unescaped via
`json.loads('"' + raw + '"')` before the inner JSON is parsed.

Discovery lead (wave 3, bare hostname `olx.ua`). curl_cffi
impersonate=chrome124 clears with a clean HTTP 200, no UA-resident IP
needed.

Pagination is `?page=N`, 52 ads per page. Enumerability confirmed live
2026-09-06: page 1 vs page 2 of `elektronika/` return disjoint ad-id sets.

Each ad's `price.regularPrice` carries a clean numeric `value` + ISO
`currencyCode` (UAH) -- no locale-string parsing needed (the human-readable
`displayValue`, e.g. "111 900 грн.", is present but unused).

Scoped in-spider to 6 consumer-goods top-level categories (electronics,
home & garden, hobby/sport/tourism, kids' world, fashion & style,
animals) -- real estate (nedvizhimost), transport, transport parts,
jobs (rabota), services (uslugi), short-term housing rental and
barter/free-giveaway sections are excluded as out of scope for a retail
price basket.

Page family parsed: listing only (individual ad PDPs are never fetched;
the `url` field is the platform's own permalink, read straight out of the
listing payload).

channel=marketplace (classifieds -- seller-authored names, all COICOP
divisions represented across categories).
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.olx.ua"
_CATEGORIES = [
    "elektronika",
    "dom-i-sad",
    "hobbi-otdyh-i-sport",
    "detskiy-mir",
    "moda-i-stil",
    "zhivotnye",
]
MAX_PAGES = 30

_STATE_RE = re.compile(r'__PRERENDERED_STATE__=\s*"(.*?)"\s*;\s*window', re.DOTALL)


class OlxUaSpider(scrapy.Spider):
    name = "olx_ua"
    allowed_domains = ["olx.ua"]
    currency = "UAH"
    language = "uk"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }
    IMPERSONATE_PROFILE = "chrome124"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_ids: set[int] = set()

    async def start(self):
        for slug in _CATEGORIES:
            yield scrapy.Request(
                f"{_BASE}/uk/{slug}/",
                callback=self.parse_listing,
                meta={"slug": slug, "page": 1, "impersonate": self.IMPERSONATE_PROFILE},
            )

    def parse_listing(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]

        m = _STATE_RE.search(response.text)
        if not m:
            logger.warning("olx_ua: no __PRERENDERED_STATE__ on %s", response.url)
            return
        try:
            state = json.loads(json.loads('"' + m.group(1) + '"'))
        except ValueError:
            logger.warning("olx_ua: unparseable state on %s", response.url)
            return

        ads = state.get("listing", {}).get("listing", {}).get("ads", [])
        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for ad in ads:
            ad_id = ad.get("id")
            title = ad.get("title")
            url = ad.get("url")
            price_block = (ad.get("price") or {}).get("regularPrice") or {}
            value = price_block.get("value")
            currency = price_block.get("currencyCode")
            if ad_id is None or not title or not url or value is None or not currency:
                continue
            if ad_id in self.seen_ids:
                continue
            self.seen_ids.add(ad_id)
            n += 1
            yield {
                "product_id": str(ad_id),
                "product_name": str(title)[:500],
                "category": slug,
                "price": str(value),
                "currency": currency,
                "available": ad.get("isActive", True),
                "url": url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info("olx_ua: %s page=%d rows=%d", slug, page, n)

        if n > 0 and page < MAX_PAGES:
            yield scrapy.Request(
                f"{_BASE}/uk/{slug}/?page={page + 1}",
                callback=self.parse_listing,
                meta={
                    "slug": slug,
                    "page": page + 1,
                    "impersonate": self.IMPERSONATE_PROFILE,
                },
            )
