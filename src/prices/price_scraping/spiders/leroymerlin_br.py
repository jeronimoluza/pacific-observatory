"""
Spider for Leroy Merlin Brazil -- https://www.leroymerlin.com.br/.

DataDome-protected: chrome124/chrome120 curl_cffi impersonation both 403
("Please enable JS and disable any ad blocker"); only safari17_0 clears it
(confirmed live 2026-08-17 on both '/' and a category page).

Category pages are server-rendered with a full Algolia InstantSearch
response embedded inline (the site's search widget hydrates from it
client-side): a `"results":[{"hits":[...],"nbHits":N,"nbPages":N,"page":N,
"hitsPerPage":N,...}]` JSON block appears twice in the HTML -- the first
occurrence is an empty placeholder (nbHits=0), the second carries the real
hits. `?page=N` on the category URL (1-indexed) changes which page the SSR
embeds (confirmed live: page=1 and page=2 returned fully disjoint
objectID sets).

No `price` field on the hit; pricing lives in `medianPromotionalPrice`
(site-wide reference price, confirmed equal to
regionalAttributes.grande_sao_paulo.promotionalPrice, the largest metro)
with `averagePromotionalPrice` as a fallback.

Category discovery: the CDN sitemap index (cdn.leroymerlin.com.br,
therefore in allowed_domains) lists departamentos_1.xml..._10.xml; only
_1.xml is fetched here (216 clean single-segment category slugs, e.g.
/ar-condicionado) sampled at a fixed stride to stay bounded -- the deeper
faceted URLs in the same file (/ar-condicionado/tipo-de-ar-condicionado/...)
are skipped.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.leroymerlin.com.br"
_SITEMAP_URL = "https://cdn.leroymerlin.com.br/sitemaps/departamentos_1.xml"
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_RESULTS_KEY = '"results":['
_CATEGORY_STRIDE = 5  # sample every Nth category slug (~43 categories)
MAX_PAGES_PER_CATEGORY = 3
IMPERSONATE_PROFILE = "safari17_0"


def _extract_result_block(text: str) -> dict | None:
    for m in re.finditer(re.escape(_RESULTS_KEY), text):
        start = m.start() + len(_RESULTS_KEY) - 1  # position of the opening '['
        try:
            obj, _ = json.JSONDecoder().raw_decode(text[start:])
        except json.JSONDecodeError:
            continue
        if obj and obj[0].get("nbHits", 0) > 0:
            return obj[0]
    return None


class LeroymerlinBrSpider(scrapy.Spider):
    name = "leroymerlin_br"
    allowed_domains = ["leroymerlin.com.br", "cdn.leroymerlin.com.br"]
    currency = "BRL"
    language = "pt"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
        },
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            _SITEMAP_URL,
            callback=self.parse_sitemap,
            meta={"impersonate": IMPERSONATE_PROFILE},
        )

    def parse_sitemap(self, response):
        locs = _LOC_RE.findall(response.text)
        slugs = [
            loc
            for loc in locs
            if loc.startswith(f"{_BASE}/")
            and loc.count("/") == 3
            and loc != f"{_BASE}/departamentos"
        ]
        sampled = slugs[::_CATEGORY_STRIDE]
        logger.info(f"{self.name}: sampled {len(sampled)}/{len(slugs)} categories")
        for slug in sampled:
            yield scrapy.Request(
                f"{slug}?page=1",
                callback=self.parse_listing,
                meta={"page": 1, "base": slug, "impersonate": IMPERSONATE_PROFILE},
            )

    def parse_listing(self, response):
        page = response.meta["page"]
        base = response.meta["base"]
        block = _extract_result_block(response.text)
        if not block:
            logger.warning(f"{self.name}: no Algolia results block at {response.url}")
            return
        category = base.rsplit("/", 1)[-1].replace("-", " ")
        for hit in block.get("hits") or []:
            item = self._item(hit, category)
            if item:
                yield item
        nb_pages = block.get("nbPages", 0)
        if block.get("hits") and page < MAX_PAGES_PER_CATEGORY and page < nb_pages:
            nxt = page + 1
            yield scrapy.Request(
                f"{base}?page={nxt}",
                callback=self.parse_listing,
                meta={"page": nxt, "base": base, "impersonate": IMPERSONATE_PROFILE},
            )

    def _item(self, hit: dict, category: str | None):
        name = (hit.get("name") or "").strip()
        product_id = hit.get("objectID") or hit.get("product_id")
        if not name or not product_id:
            return None
        price = hit.get("medianPromotionalPrice") or hit.get("averagePromotionalPrice")
        if price is None:
            regional = hit.get("regionalAttributes") or {}
            sp = regional.get("grande_sao_paulo") or {}
            price = sp.get("promotionalPrice")
        if price is None:
            return None
        url = hit.get("url")
        return {
            "product_id": str(product_id),
            "product_name": name[:500],
            "category": category,
            "price": str(price),
            "currency": self.currency,
            "available": True,
            "url": f"{_BASE}/{url}"
            if url and not url.startswith("http")
            else (url or _BASE),
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
