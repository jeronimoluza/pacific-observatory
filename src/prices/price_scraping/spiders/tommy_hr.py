"""
Spider for Tommy (Croatia) — https://www.tommy.hr/.

Next.js Pages Router storefront over a Sylius Shop API v2 backend
(`/api/v2/shop/products/<code>`, referenced as `@id` inside the page's own
data, not called directly by this spider). Each product detail page
(`/proizvodi/<slug>`) is server-rendered and embeds the full product
object -- name, variant price (integer cents), currency, breadcrumb -- in
a React Query cache dehydrated into `<script id="__NEXT_DATA__">`.

Verified live 2026-09-06: GET /proizvodi/jabuka-granny-smith-1-kg -> 200,
`__NEXT_DATA__.props.pageProps.dehydratedState.queries[0].state.data` is
the Product object directly: code "291577", name "Jabuka Granny Smith 1
kg", variants[0].price 109 (EUR cents -> 1.09), breadcrumb "voce-i-
povrce/voce/jabuka-granny-smith-1-kg". Price is definitely minor units
(cents), not thousandths -- 109 -> EUR 1.09/kg matches a plausible apple
price; the same field also carries originalPrice 169 (pre-discount).

URL seeding: /sitemap.xml -> sitemap-0.xml (5000 URLs, ~4773 `/proizvodi/`)
+ sitemap-1.xml (415 more) = ~5188 product pages total.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.tommy.hr"
_SITEMAPS = [f"{_BASE}/sitemap-0.xml", f"{_BASE}/sitemap-1.xml"]
_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)


class TommyHrSpider(scrapy.Spider):
    name = "tommy_hr"
    allowed_domains = ["tommy.hr"]
    currency = "EUR"
    language = "hr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        for sm_url in _SITEMAPS:
            yield scrapy.Request(sm_url, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        locs = re.findall(r"<loc>([^<]+)</loc>", response.text)
        prod_urls = [u for u in locs if "/proizvodi/" in u]
        logger.info(f"tommy_hr: {response.url} -> {len(prod_urls)} product urls")
        for u in prod_urls:
            yield scrapy.Request(u, callback=self.parse_product)

    def parse_product(self, response):
        m = _NEXT_DATA_RE.search(response.text)
        if not m:
            logger.warning(f"tommy_hr: no __NEXT_DATA__ on {response.url}")
            return
        try:
            data = json.loads(m.group(1))
            queries = data["props"]["pageProps"]["dehydratedState"]["queries"]
            product = next(
                q["state"]["data"]
                for q in queries
                if isinstance(q.get("state", {}).get("data"), dict)
                and q["state"]["data"].get("@type") == "Product"
            )
        except (KeyError, IndexError, StopIteration, TypeError) as exc:
            logger.warning(f"tommy_hr: parse failed on {response.url}: {exc}")
            return

        variants = product.get("variants") or []
        if not variants:
            return
        variant = variants[0]
        price_minor = variant.get("price")
        if price_minor is None:
            return

        yield {
            "product_id": product.get("code"),
            "product_name": (product.get("name") or "").strip()[:500],
            "category": (product.get("breadcrumb") or "").split("/")[0] or None,
            "price": round(price_minor / 100, 2),
            "currency": variant.get("priceCurrency") or self.currency,
            "available": True,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
