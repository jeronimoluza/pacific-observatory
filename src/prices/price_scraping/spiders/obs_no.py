"""
Obs (Coop Norge's hypermarket chain), https://www.obs.no/ — Norway.

Coop Norge's corporate site (coop.no) has no webshop; Coop's home-delivery
service (matlevering.coop.no) requires login. Obs is one of Coop's six
in-store chain concepts (a hypermarket format) and runs its own public
non-food webshop (home, kitchen, garden, sport, toys, electronics -- click
& collect / delivery, no groceries) on a "Nitro"/"glitz" bundled frontend.
No open product-search API found, but https://www.obs.no/sitemap.xml
chains to https://www.obs.no/sitemap.xml?batch=<n>&language=nb-no (n=0..2,
~18.9k distinct PDP URLs after de-duping repeated <loc> entries within a
batch). Each PDP embeds a schema.org ProductGroup JSON-LD block
server-side: one `hasVariant` entry per SKU (color/size), each with its own
Offer (price/priceCurrency/availability). Sample verified live 2026-08-31:
'SPiiS termoflaske' sku Obs-7025180685673 -> NOK 99.90, InStock. A sibling
BreadcrumbList JSON-LD's last entry is the leaf category. product_id is the
per-variant `sku` (e.g. "Obs-7025180685673"), which is unique.
"""

import html
import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP_URL_TMPL = "https://www.obs.no/sitemap.xml?batch={n}&language=nb-no"
_MAX_SITEMAP_BATCHES = 5  # safety cap; chain is 3 batches (0..2) as of 2026-08-31
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_LDJSON_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>\s*(.*?)\s*</script>',
    re.DOTALL,
)


class ObsNoSpider(scrapy.Spider):
    name = "obs_no"
    allowed_domains = ["obs.no", "www.obs.no"]
    currency = "NOK"
    language = "no"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 16,
        "DOWNLOAD_DELAY": 0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        seen_urls = set()
        for n in range(_MAX_SITEMAP_BATCHES):
            yield scrapy.Request(
                _SITEMAP_URL_TMPL.format(n=n),
                callback=self.parse_sitemap,
                errback=self._ignore_missing_batch,
                meta={"batch": n, "seen": seen_urls},
                dont_filter=True,
            )

    def _ignore_missing_batch(self, failure):
        logger.info("obs_no: sitemap batch missing (%s), stopping chain", failure.value)

    def parse_sitemap(self, response):
        if response.status != 200:
            return
        seen_urls = response.meta["seen"]
        urls = _LOC_RE.findall(response.text)
        new_urls = [u for u in urls if u not in seen_urls]
        seen_urls.update(new_urls)
        logger.info(
            "obs_no: %d URLs on batch %s (%d new)",
            len(urls),
            response.meta.get("batch"),
            len(new_urls),
        )
        for url in new_urls:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        product_group = None
        breadcrumb = None
        for block in _LDJSON_RE.findall(response.text):
            data = self._loads(block)
            if not isinstance(data, dict):
                continue
            if data.get("@type") in ("ProductGroup", "Product"):
                product_group = data
            elif data.get("@type") == "BreadcrumbList":
                breadcrumb = data

        if not product_group:
            return

        name = product_group.get("name")
        if not name:
            return
        clean_name = html.unescape(str(name)).strip()[:500]

        category = None
        if breadcrumb:
            items = breadcrumb.get("itemListElement") or []
            if items:
                leaf = items[-1].get("item") or {}
                if isinstance(leaf, dict):
                    category = leaf.get("name")
        category = html.unescape(str(category)) if category else None

        variants = product_group.get("hasVariant") or [product_group]
        scraped_at = datetime.now(timezone.utc).isoformat()
        for variant in variants:
            offers = variant.get("offers") or {}
            price = offers.get("price")
            sku = variant.get("sku")
            if not sku or price in (None, "", 0, "0"):
                continue
            yield {
                "product_id": str(sku),
                "product_name": clean_name,
                "category": category,
                "price": str(price),
                "currency": offers.get("priceCurrency") or self.currency,
                "available": str(offers.get("availability", "")).endswith("InStock"),
                "url": offers.get("url") or response.url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

    @staticmethod
    def _loads(block):
        try:
            return json.loads(block)
        except (ValueError, TypeError):
            return None
