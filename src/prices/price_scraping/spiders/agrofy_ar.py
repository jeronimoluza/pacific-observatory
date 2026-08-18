"""
Spider for Agrofy Argentina (Argentina) -- https://www.agrofy.com.ar/.

Shard entry `agrofy.com.co` (nominally Colombia) 301s to agrofy.com:443
then 302s to www.agrofy.com.ar with no Colombia-specific catalog at all --
the .co domain is dead weight on top of the real Argentina site. Shipped
here as Argentina (not skipped) because agrofy.com.ar is a distinct,
substantial catalog -- same Agrofy platform as agrofy_br.py but a different
country's used farm-machinery inventory, not a duplicate of the Brazil
listings. Real-estate ("campos") and services/financing categories are
excluded, matching the agrofy_br.py convention.

Same `__NEXT_DATA__` JSON-in-HTML structure as agrofy_br.py. Pagination is
`?p=N` (verified live 2026-08-17, same as .br).

Gotcha: currency is NOT uniform. Listings mix ARS ("$") and USD ("U$")
per-item -- e.g. a used tractor priced in pesos next to an imported
combine priced in dollars, both in the same category page. The shard's
"ARS ($)" currency column is only half right; this spider reads the
per-hit `currency` field and maps '$' -> ARS, 'U$' -> USD rather than
hardcoding one currency for the whole source.
"""

import json
import logging
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.agrofy.com.ar"
_CATEGORIES = [
    "tractores",
    "tractores-usados",
    "cosechadoras",
    "sembradoras",
    "pulverizadoras",
    "rastras",
    "desmalezadoras",
    "tolvas",
    "mixers",
    "rolos",
]
MAX_PAGES_PER_CATEGORY = 20
_CURRENCY_MAP = {"$": "ARS", "U$": "USD"}


class AgrofyArSpider(scrapy.Spider):
    name = "agrofy_ar"
    allowed_domains = ["agrofy.com.ar"]
    language = "es"

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
        self.seen_ids = set()
        for slug in _CATEGORIES:
            yield scrapy.Request(
                f"{_BASE}/{slug}",
                callback=self.parse_category,
                meta={"slug": slug, "page": 1},
            )

    def parse_category(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]
        raw = response.css("script#__NEXT_DATA__::text").get()
        if not raw:
            logger.warning(f"{self.name}: no __NEXT_DATA__ at {response.url}")
            return
        try:
            data = json.loads(raw)["props"]["pageProps"]
        except (json.JSONDecodeError, KeyError):
            logger.warning(f"{self.name}: malformed __NEXT_DATA__ at {response.url}")
            return
        hits = data.get("listing", {}).get("Hits") or []
        for hit in hits:
            item_id = hit.get("id")
            name = (hit.get("name") or "").strip()
            price = hit.get("price")
            url = hit.get("url")
            if item_id is None or not name or price is None or not url:
                continue
            # price=0 marks "A Convenir" (price on request / negotiated
            # financing) listings, not a parse failure -- confirmed live
            # 2026-08-17 (paymentMethod="A Convenir."). A 0 price is worse
            # than no row, so skip rather than emit it.
            try:
                if float(price) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            if item_id in self.seen_ids:
                continue
            self.seen_ids.add(item_id)
            currency = _CURRENCY_MAP.get((hit.get("currency") or "").strip(), "ARS")
            yield {
                "product_id": str(item_id),
                "product_name": name[:500],
                "category": hit.get("categoryName") or slug,
                "price": str(price),
                "currency": currency,
                "available": True,
                "url": urljoin(_BASE, url),
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        if hits and page < MAX_PAGES_PER_CATEGORY:
            yield scrapy.Request(
                f"{_BASE}/{slug}?p={page + 1}",
                callback=self.parse_category,
                meta={"slug": slug, "page": page + 1},
            )
