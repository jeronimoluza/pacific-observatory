"""
Spider for OLX Poland (www.olx.pl) -- consumer-goods classifieds.

Same OLX Group platform as olx_pk / olx.ro (see those spiders) but a
different frontend generation: category listing pages are React SSR and
embed the full result set as a JSON-in-JS-string blob,
`window.__PRERENDERED_STATE__= "<escaped JSON>"`, at
`listing.listing.ads[]`. The string is JS-escaped (backslash-escaped
quotes/unicode), so it is unescaped via `json.loads('"' + raw + '"')`
before the inner JSON is parsed.

The shard's original probe hit a generic CloudFront "Request blocked"
stub; curl_cffi impersonate=chrome124 did not reproduce that at all --
homepage and category pages both cleared at 200 on the first try, no
challenge round-trip needed.

Pagination is `?page=N`. Enumerability confirmed live 2026-08-17: page 1
vs page 2 of elektronika/ share only 2 of 52 ad ids -- materially
different.

Each ad's `price.regularPrice` is already a clean numeric value + ISO
currency code (PLN) -- no locale-string parsing needed.

Scoped in-spider to 6 consumer-goods top-level categories (electronics,
fashion, kids, pets, agriculture/garden, music & education) -- vehicles,
real estate, jobs and services are not in this list (dom-i-ogrod and
sport-hobby-turystyka 404 as top-level slugs on this site and are not
used either).
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.olx.pl"
_CATEGORIES = [
    "elektronika",
    "moda",
    "dla-dzieci",
    "zwierzeta",
    "rolnictwo",
    "muzyka-edukacja",
]
MAX_PAGES = 25

_STATE_RE = re.compile(r'__PRERENDERED_STATE__=\s*"(.*?)"\s*;\s*window', re.DOTALL)


class OlxPlSpider(scrapy.Spider):
    name = "olx_pl"
    allowed_domains = ["olx.pl"]
    currency = "PLN"
    language = "pl"

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
            logger.warning("olx_pl: no __PRERENDERED_STATE__ on %s", response.url)
            return
        try:
            state = json.loads(json.loads('"' + m.group(1) + '"'))
        except ValueError:
            logger.warning("olx_pl: unparseable state on %s", response.url)
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
        logger.info("olx_pl: %s page=%d rows=%d", slug, page, n)

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
