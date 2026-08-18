"""
Spider for OLX Romania (www.olx.ro) -- consumer-goods classifieds.

Same OLX Group platform and same frontend generation as olx.pl (see
olx_pl.py): category listing pages are React SSR and embed the full result
set as a JSON-in-JS-string blob, `window.__PRERENDERED_STATE__= "<escaped
JSON>"`, at `listing.listing.ads[]`. The string is JS-escaped, so it is
unescaped via `json.loads('"' + raw + '"')` before the inner JSON is parsed.

Bare curl gets a Cloudflare "Just a moment" 403; curl_cffi
impersonate=chrome124 clears it fully.

Pagination is `?page=N`, 52 ads per page. Enumerability confirmed live
2026-08-17: page 1 vs page 2 of electronice-si-electrocasnice/ return
disjoint ad-id sets.

GOTCHA -- this spider originally parsed the schema.org `Offer` objects in
the page's JSON-LD block. That block is SEO markup: it exists ONLY on
page 1 and lists only 20 of the 52 ads. Pages 2+ are full 3.3MB documents
containing zero `@type":"Offer"` occurrences, so the parser found nothing,
the "stop when a page yields no new ids" rule fired immediately, and the
spider exited `finished` after 12 requests with 119 rows. Do not go back
to the JSON-LD block -- `__PRERENDERED_STATE__` is the real payload.

Each ad's `price.regularPrice` is already a clean numeric value + ISO
currency code (RON) -- no locale-string parsing needed.

Scoped in-spider to 6 consumer-goods top-level categories (electronics,
home & garden, hobby/sport/tourism, mother & child, fashion/beauty,
pets) -- vehicles (auto-masini-moto-ambarcatiuni), real estate
(imobiliare), auto parts (piese-auto), jobs (locuri-de-munca), services
and rentals are excluded as out of scope for a retail price basket.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.olx.ro"
_CATEGORIES = [
    "electronice-si-electrocasnice",
    "casa-gradina",
    "hobby-sport-turism",
    "mama-si-copilul",
    "moda-frumusete",
    "animale-de-companie",
]
MAX_PAGES = 30

_STATE_RE = re.compile(r'__PRERENDERED_STATE__=\s*"(.*?)"\s*;\s*window', re.DOTALL)


class OlxRoSpider(scrapy.Spider):
    name = "olx_ro"
    allowed_domains = ["olx.ro"]
    currency = "RON"
    language = "ro"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
        },
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
                f"{_BASE}/{slug}/",
                callback=self.parse_listing,
                meta={"slug": slug, "page": 1, "impersonate": self.IMPERSONATE_PROFILE},
            )

    def parse_listing(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]

        m = _STATE_RE.search(response.text)
        if not m:
            logger.warning("olx_ro: no __PRERENDERED_STATE__ on %s", response.url)
            return
        try:
            state = json.loads(json.loads('"' + m.group(1) + '"'))
        except ValueError:
            logger.warning("olx_ro: unparseable state on %s", response.url)
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
        logger.info("olx_ro: %s page=%d rows=%d", slug, page, n)

        if n > 0 and page < MAX_PAGES:
            yield scrapy.Request(
                f"{_BASE}/{slug}/?page={page + 1}",
                callback=self.parse_listing,
                meta={
                    "slug": slug,
                    "page": page + 1,
                    "impersonate": self.IMPERSONATE_PROFILE,
                },
            )
