"""
Nemlig.com (Denmark) — https://www.nemlig.com/.

Denmark's largest pure-play online supermarket. The storefront is a
client-rendered SPA (the home page and every `/dagligvarer/...` category page
return a ~14 KB shell with no product markup), but two things are open over
plain HTTP:

  * `robots.txt` advertises `https://www.nemlig.com/googleproductsitemap`,
    a flat urlset of **13,306 product URLs** (measured 2026-09-11), all of
    the shape `/<slug>-<numeric id>`; and
  * each of those PDPs is **server-rendered** and carries a
    `schema.org/Product` JSON-LD block with `name`, `brand`, `category`,
    `description` (pack size / producer / best-before) and
    `offers.price` + `offers.priceCurrency`.

So the spider is a sitemap walk plus a JSON-LD read — no API key, no
Playwright, no JWT. This deliberately sidesteps the two routes that an
earlier pass found walled (recorded in `references/known_blockers.md`): the
`/webapi/<stamp>/<TimeslotUtc>/<DeliveryZoneId>/...Products/...` route, whose
parameters only exist after a delivery-address + timeslot booking flow, and
`webapi.prod.knl.nemlig.it/searchgateway/api/search`, which 401s with
"Jwt is missing". The Google product sitemap needs neither.

**Queue-it warm-up is mandatory and is the whole trick here.** The site is
fronted by a Queue-it virtual waiting room running as a Cloudflare worker
(`kupver=cloudflare-4.2.2`). A cold request to any PDP 302s to
`nemlig.queue-it.net` — measured 12 of 12 cold, and a first version of this
spider took 219 such redirects and scraped 0 items. Fetching the home page
once sets `QueueITAccepted-SDFrts345E-V3_nemligprod` (plus `Queue-it-token`,
`Queue-it-visitorsession`); with that cookie in the jar every subsequent PDP
returns 200 — measured 12 of 12 at 0.5 s/request and 12 of 12 at 1.0 s/request.
Hence `start()` fetches `/` first and only then the sitemap, and
`COOKIES_ENABLED` must stay on. A PDP that still lands on `queue-it.net` is
logged and dropped rather than parsed.

Prices are plain decimal DKK taken from the page's own `priceCurrency` (not
assumed from `countries.yaml`) — no minor-unit division. Verified live
2026-09-11, 6 of 6 sampled PDPs parsed: 'Coca-Cola Zero Koffeinfri' DKK 18
(category 'Drikke'), 'Parmaskinke øko.' DKK 59.95 ('Køl'), 'Akacie honning
øko.' DKK 100 ('Kolonial'), 'Nødder salte og søde' DKK 48.33 ('Kiosk').

Catalogue is a full supermarket assortment (kolonial, køl, frost, drikke,
frugt & grønt, personlig pleje, husholdning, kiosk) — wide, left to the
classifier. The JSON-LD `category` is the top-level department only, which
is coarse but is a real breadcrumb value rather than an invented one.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.nemlig.com"
SITEMAP_URL = f"{BASE_URL}/googleproductsitemap"
_LOC_RE = re.compile(r"<loc>(.*?)</loc>", re.S)
_LDJSON_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.S
)
_ID_RE = re.compile(r"-(\d+)$")


def _iter_ldjson(text: str):
    for blob in _LDJSON_RE.findall(text):
        try:
            parsed = json.loads(blob)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(parsed, list):
            yield from (o for o in parsed if isinstance(o, dict))
        elif isinstance(parsed, dict):
            yield parsed


class NemligDkSpider(scrapy.Spider):
    name = "nemlig_dk"
    allowed_domains = ["nemlig.com"]
    currency = "DKK"
    language = "da"

    custom_settings = {
        # Cookies carry the Queue-it acceptance token — never disable these.
        "COOKIES_ENABLED": True,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        # Warm-up: sets the Queue-it acceptance cookie for the whole crawl.
        yield scrapy.Request(
            f"{BASE_URL}/",
            callback=self.parse_home,
            errback=self.errback,
            dont_filter=True,
        )

    def parse_home(self, response):
        logger.info(f"{self.name}: warm-up {response.status} on {response.url}")
        yield scrapy.Request(
            SITEMAP_URL,
            callback=self.parse_sitemap,
            errback=self.errback,
            dont_filter=True,
        )

    def parse_sitemap(self, response):
        urls = _LOC_RE.findall(response.text)
        logger.info(f"{self.name}: {len(urls)} product URLs in the sitemap")
        for url in urls:
            yield scrapy.Request(
                url.strip(), callback=self.parse_product, errback=self.errback
            )

    def parse_product(self, response):
        if "queue-it" in response.url:
            logger.warning(f"{self.name}: queued by Queue-it — {response.url[:120]}")
            return

        product = None
        for obj in _iter_ldjson(response.text):
            if obj.get("@type") == "Product":
                product = obj
                break
        if product is None:
            logger.warning(f"{self.name}: no Product JSON-LD on {response.url}")
            return

        offers = product.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        price = offers.get("price")
        name = (product.get("name") or "").strip()
        if not name or price in (None, ""):
            logger.warning(f"{self.name}: no name/price on {response.url}")
            return

        pid = _ID_RE.search(response.url.rstrip("/"))
        # The site states its own currency; do not assume it from countries.yaml.
        currency = offers.get("priceCurrency") or self.currency

        yield {
            "product_id": pid.group(1) if pid else None,
            "product_name": name[:500],
            "category": product.get("category"),
            "price": str(price),
            "currency": currency,
            "available": "InStock" in str(offers.get("availability") or ""),
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
