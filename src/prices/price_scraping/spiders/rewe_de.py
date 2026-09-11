"""
Spider for REWE (Germany) — https://www.rewe.de/shop/, Germany's largest
grocery-delivery storefront and (as of this batch) Germany's first
first-party grocery source in the tree.

The repo-pinned chrome120 profile (and chrome124/chrome131/chrome99/chrome110/
chrome116/chrome131_android) all 403 on shop.rewe.de's edge; chrome133a and
chrome119 return 200 (probed live 2026-09-10). No prior session/cookie warm-up
is needed -- a cold curl_cffi request straight to the sitemap or a PDP with
impersonate="chrome133a" returns 200 on the first try.

URL-path gotcha: shop.rewe.de itself 404s on `/shop/...` paths (its own nav
links resolve relative to an implicit `/shop` base) -- the real, fetchable PDP
and sitemap host is `www.rewe.de` (shop.rewe.de redirects there for content
paths; only used here as the impersonate-profile probe target).

PDP's own `application/ld+json` Product node has NO `offers` block (name/
image/description/gtin/brand/sku only) -- this is NOT the standard wave-2
JSON-LD price pattern despite rewe.de looking like a fit at first probe. The
real price lives in a `<script id="pdpr-propstore<N>-<articleId>-<uuid>">`
SSR JSON blob: `{"productData":{"productName":...,"pricing":{"price":99,
"regularPrice":99},...}}` -- price is EUR cents (99 -> EUR 0.99). No explicit
currency field, but cross-verified: `pricing.grammage` embeds REWE's own
computed per-unit price in "1 l = 11,87 €" / "1 kg = 17,09 €" form, and
0.75l x 11.87 EUR/l = EUR 8.90 matches `pricing.price` 890 on the same page
(delheim-pinotage-ros-trocken-0-75l/976061) -- confirmed on 5 products across
different categories. This is a Germany-wide reference price (no delivery
postcode/session set at all in the probe) -- REWE's per-postcode dark-store
pricing may vary at the margin, but this is the same "no session" price any
anonymous visitor/bot sees.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP_INDEX = "https://www.rewe.de/sitemaps/sitemap.xml"
_LOC_RE = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.S | re.I)
_PROPSTORE_RE = re.compile(
    r'id="pdpr-propstore\d*-[^"]*">\s*(\{.*?\})\s*</script>', re.S
)


class ReweDeSpider(scrapy.Spider):
    name = "rewe_de"
    allowed_domains = ["rewe.de", "www.rewe.de", "shop.rewe.de"]
    currency = "EUR"
    language = "de"

    # chrome120 (repo default) 403s on this host's edge; chrome133a is the
    # confirmed-working profile (see module docstring). Pinning it takes all
    # three parts together, per the libdelivery_lr precedent: disable the
    # random-browser middleware (it overwrites meta["impersonate"] per
    # request), match the User-Agent to the same Chrome version (curl_cffi
    # forwards Scrapy's headers verbatim, so a chrome133 handshake under a
    # chrome120 UA is itself a 403 tell), and set IMPERSONATE_PROFILE.
    IMPERSONATE_PROFILE = "chrome133a"
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.5,
        "RETRY_TIMES": 2,
        "AUTOTHROTTLE_ENABLED": True,
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
        },
        "USER_AGENT": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
        ),
    }

    def _meta(self, extra: dict | None = None) -> dict:
        meta = dict(extra or {})
        meta["impersonate"] = self.IMPERSONATE_PROFILE
        return meta

    async def start(self):
        yield scrapy.Request(_SITEMAP_INDEX, callback=self.parse_index, meta=self._meta())

    def parse_index(self, response):
        for loc in _LOC_RE.findall(response.text):
            if "sitemap-shop-produkte" in loc:
                yield scrapy.Request(loc, callback=self.parse_shard, meta=self._meta())

    def parse_shard(self, response):
        locs = _LOC_RE.findall(response.text)
        logger.info(f"rewe_de: shard={response.url} urls={len(locs)}")
        for url in locs:
            yield scrapy.Request(url, callback=self.parse_product, meta=self._meta())

    def parse_product(self, response):
        m = _PROPSTORE_RE.search(response.text)
        if not m:
            logger.warning(f"rewe_de: no propstore block at {response.url}")
            return
        try:
            data = json.loads(m.group(1))
        except ValueError:
            logger.warning(f"rewe_de: unparseable propstore JSON at {response.url}")
            return

        pd = data.get("productData") or {}
        name = (pd.get("productName") or "").strip()
        pricing = pd.get("pricing") or {}
        price_cents = pricing.get("price")
        if not name or not price_cents:
            return

        yield {
            "product_id": pd.get("articleId") or pd.get("productId"),
            "product_name": name[:500],
            "price": str(price_cents / 100),
            "currency": self.currency,
            "category": pd.get("categorySlug"),
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
