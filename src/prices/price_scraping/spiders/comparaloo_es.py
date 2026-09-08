"""
Spider for Comparaloo (Spain) — https://comparaloo.es/.

Multi-category, multi-retailer price-comparison site (84 stores per shard
AI_NOTES). No WAF (curl_cffi impersonate="chrome124" clears with plain
headers). PDPs are server-rendered Next.js pages with a clean
`application/ld+json` `Product` block:

    {"@type":"Product","name":"...","offers":{"@type":"Offer",
     "priceCurrency":"EUR","price":"5.88",...,
     "seller":{"@type":"Organization","name":"Sedovin"}}}

Grocery/supermarket PDP URLs are enumerated by `sitemap-supermarket.xml`
(10.6MB, tens of thousands of `<loc>` entries, `changefreq: daily`) — this is
the catalog walk; category pages like `/groceries` are client-rendered
(React Server Components, no product links in the static HTML) and are not
used. `seller.name` is the first-party retailer actually selling the item
(e.g. "Sedovin"); `category` is left null since there's no reliable
breadcrumb, and comparaloo itself spans many divisions, so
`channel: marketplace`.

Re-verified live 2026-09-06: sitemap-supermarket.xml -> 200, 10.6MB; sample
PDP https://comparaloo.es/product/sedovin-galletas-danesas-de-mantequilla-
royal-ballet-lata-454-g-... -> 200, JSON-LD price 5.88 EUR, seller "Sedovin".
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://comparaloo.es"
_SITEMAP = f"{_BASE}/sitemap-supermarket.xml"
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_LDJSON_RE = re.compile(
    r'<script type="application/ld\+json">(\{"@context":"https://schema\.org","@type":"Product".*?)</script>',
    re.S,
)
MAX_URLS = 5000  # safety cap on one sitemap pass; sitemap itself is ~50k+ urls


class ComparalooEsSpider(scrapy.Spider):
    name = "comparaloo_es"
    allowed_domains = ["comparaloo.es"]
    currency = "EUR"
    language = "es"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(_SITEMAP, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        urls = _LOC_RE.findall(response.text)[:MAX_URLS]
        logger.info(f"comparaloo_es: {len(urls)} product urls in sitemap (capped)")
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        m = _LDJSON_RE.search(response.text)
        if not m:
            logger.warning(f"comparaloo_es: no Product JSON-LD at {response.url}")
            return
        try:
            data = json.loads(m.group(1))
        except ValueError:
            logger.warning(f"comparaloo_es: malformed JSON-LD at {response.url}")
            return
        offer = data.get("offers") or {}
        price = offer.get("price")
        name = data.get("name")
        if not price or not name:
            return
        seller = (offer.get("seller") or {}).get("name")
        product_id = response.url.rstrip("/").rsplit("/", 1)[-1]
        scraped_at = datetime.now(timezone.utc).isoformat()
        yield {
            "product_id": product_id,
            "product_name": name.strip()[:500],
            "category": seller,
            "price": str(price),
            "currency": offer.get("priceCurrency") or self.currency,
            "available": offer.get("availability", "").endswith("InStock"),
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
