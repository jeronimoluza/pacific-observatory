"""
My Market — https://www.mymarket.gr/ (Greek supermarket chain, part of the
Kritikos group).

Server-rendered storefront (the homepage sits behind an Incapsula bot-
mitigation resource, but curl_cffi impersonate="chrome124" clears it on
every request with no cookies/proxy needed -- a genuine WAF was never
actually hit). Two extraction paths were probed:

1. The site publishes a full product sitemap (sitemap/products.xml,
   15,267 PDP urls) with a schema.org Product JSON-LD per PDP -- but that
   single file is ~8MB and was repeatedly flaky live (curl_cffi timeouts
   and a run of HTTP 429s fetching it, even though the homepage and
   individual PDPs kept returning 200 throughout), so it is NOT the path
   this spider uses.
2. Category leaf pages (from sitemap/categories.xml, 543 leaves) instead
   embed a schema.org `ItemList` JSON-LD directly on the listing page,
   with a fully-populated nested `Product` (name/sku/category/offers) per
   list item -- no per-PDP request needed at all. Verified sample: the
   `/gala` (milk) leaf's ItemList carries 35 items, e.g. 'My Kouzina
   Συμπυκνωμένο Easy Open Γάλα Light 410gr' sku 250223, EUR 0.94, InStock.

Pagination: each category page renders ~34 items per page. The ItemList's
own `numberOfItems` matches only the CURRENT page's item count, not the
category total -- broader leaves like `/trofima` (grocery staples) run to
58 pages. Followed the server's own `<a rel="next" href="...?page=N">`
cursor (present on the page's Pagination Navigation) rather than
synthesizing a counter; the last page simply has no `rel="next"` anchor
(verified: /trofima?page=58 has 23 items and no next link).
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_CATEGORIES_SITEMAP = "https://www.mymarket.gr/sitemap/categories.xml"
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_LDJSON_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>\s*(.*?)\s*</script>',
    re.DOTALL,
)


class MymarketGrSpider(scrapy.Spider):
    name = "mymarket_gr"
    allowed_domains = ["www.mymarket.gr"]
    currency = "EUR"
    language = "el"

    custom_settings = {
        # Incapsula throttles aggressively at higher concurrency (measured:
        # 37/57 responses came back 429 at CONCURRENT_REQUESTS_PER_DOMAIN=4).
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.5,
        "RETRY_TIMES": 5,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 1.0,
    }

    async def start(self):
        yield scrapy.Request(
            _CATEGORIES_SITEMAP, callback=self.parse_categories, errback=self.errback
        )

    def parse_categories(self, response):
        if response.status != 200:
            logger.error(
                f"{self.name}: non-200 ({response.status}) fetching categories sitemap"
            )
            return
        urls = _LOC_RE.findall(response.text)
        logger.info(f"{self.name}: {len(urls)} category urls in sitemap")
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_listing, errback=self.errback)

    def parse_listing(self, response):
        content_type = response.headers.get("Content-Type", b"").decode("latin1")
        if response.status != 200 or "html" not in content_type.lower():
            logger.warning(
                f"{self.name}: non-HTML response (status={response.status}, "
                f"content-type={content_type!r}) on {response.url}, skipping"
            )
            return

        item_list = None
        for block in _LDJSON_RE.findall(response.text):
            data = self._loads(block)
            if not isinstance(data, dict):
                continue
            graph = data.get("@graph")
            if not isinstance(graph, list):
                continue
            for g in graph:
                if isinstance(g, dict) and g.get("@type") == "ItemList":
                    item_list = g
                    break
            if item_list:
                break

        found = 0
        if item_list:
            for entry in item_list.get("itemListElement") or []:
                product = (entry or {}).get("item") or {}
                if product.get("@type") != "Product":
                    continue

                offers = product.get("offers") or {}
                price = offers.get("price")
                name = product.get("name")
                product_id = product.get("sku")
                url = product.get("url")
                if not name or not product_id or not url or price in (None, "", 0, "0"):
                    continue

                found += 1
                yield {
                    "product_id": str(product_id),
                    "product_name": str(name).strip()[:500],
                    "category": product.get("category"),
                    "price": str(price),
                    "currency": offers.get("priceCurrency") or self.currency,
                    "available": str(offers.get("availability", "")).endswith(
                        "InStock"
                    ),
                    "url": url,
                    "language": self.language,
                    "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
                }

        logger.info(f"{self.name}: {response.url} yielded={found}")

        next_href = response.css('a[rel="next"]::attr(href)').get()
        if next_href:
            yield response.follow(
                next_href, callback=self.parse_listing, errback=self.errback
            )

    @staticmethod
    def _loads(block):
        try:
            return json.loads(block)
        except (ValueError, TypeError):
            return None

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
