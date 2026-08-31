"""
Lulu Hypermarket Bahrain — https://gcc.luluhypermarket.com/en-bh/.

Next.js (app router) storefront on the Akinon commerce platform
(bf1af2.akinoncloudcdn.com asset host). Product-detail pages render a
schema.org Product JSON-LD block, but it is always a placeholder
("price": "0.00", "priceCurrency": null) regardless of real stock/price —
do not trust it.

The real catalog data is embedded server-side as an escaped JSON string
inside a React Server Components stream (`self.__next_f.push([1, "..."])`
script tags) on *category listing* pages. Each product entry there carries
`name`, `sku`, `price`, `in_stock`, `currency_type` ("bhd"), `retail_price`
and `absolute_url`, plus locale-specific attributes such as
`shipment_type_bahrain` confirming this is genuinely the Bahrain storefront
(not a GCC-wide fallback). No JSON API endpoint was found — the RSC payload
on the rendered HTML is the extraction surface (Tier 1A).

Category URLs are discovered from the storefront's own sitemap
(`/en-bh/sitemap/categories-1`, 486 category URLs spanning the whole tree
from top departments down to leaf categories). Each category page is
walked with `?page=N`; a `?page=N` query different from the plain URL does
return a different product set (verified: page=1 gave 51 distinct SKUs,
page=2 a different 52), so pagination genuinely advances. A category stops
once a page contributes zero NEW product ids (a page far past the real
last page degrades to ~1 spurious match, confirmed at page=10 on a
52-product category), capped at MAX_PAGES_PER_CATEGORY as a hard safety
limit. Products cross-listed under parent AND child categories are
naturally deduplicated downstream by the DuplicationPipeline on `url`.

Rows with price "0.00" (out-of-stock placeholder, `in_stock: false`) are
dropped — they measure nothing.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://gcc.luluhypermarket.com"
SITEMAP_URL = f"{BASE_URL}/en-bh/sitemap/categories-1"
MAX_PAGES_PER_CATEGORY = 10

_LOC_RE = re.compile(r"<loc>(.*?)</loc>")
_PRODUCT_RE = re.compile(
    r'\\"name\\":\\"(?P<name>[^\\]*?)\\",\\"sku\\":\\"(?P<sku>[^\\"]+)\\"'
    r'.{0,10000}?\\"price\\":\\"(?P<price>[\d.]+)\\",\\"in_stock\\":(?P<in_stock>true|false),'
    r'\\"currency_type\\":\\"(?P<currency>[a-z]*)\\",\\"retail_price\\":\\"(?P<retail>[\d.]+)\\"'
    r'.{0,2000}?\\"absolute_url\\":\\"(?P<url>[^\\"]+)\\"',
    re.DOTALL,
)


class LuluBhSpider(scrapy.Spider):
    name = "lulu_bh"
    allowed_domains = ["luluhypermarket.com"]
    currency = "BHD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            SITEMAP_URL, callback=self.parse_sitemap, errback=self.errback
        )

    def parse_sitemap(self, response):
        locs = _LOC_RE.findall(response.text)
        categories = sorted(set(locs))
        logger.info(f"{self.name}: categories found={len(categories)}")
        for url in categories:
            slug = url.rstrip("/").rsplit("/", 1)[-1]
            yield scrapy.Request(
                url,
                callback=self.parse_category,
                errback=self.errback,
                meta={"category": slug, "page": 1, "seen_ids": set()},
            )

    def parse_category(self, response):
        category = response.meta["category"]
        page = response.meta["page"]
        seen_ids = response.meta["seen_ids"]

        matches = list(_PRODUCT_RE.finditer(response.text))
        new_count = 0

        for match in matches:
            sku = match.group("sku")
            if sku in seen_ids:
                continue
            seen_ids.add(sku)

            if match.group("currency") != "bhd":
                continue
            price = match.group("price")
            if match.group("in_stock") != "true" or float(price) == 0:
                continue

            new_count += 1
            name = match.group("name").encode().decode("unicode_escape")
            rel_url = match.group("url")
            yield {
                "product_id": sku,
                "product_name": name[:500],
                "category": category,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": f"{BASE_URL}/en-bh{rel_url}",
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        logger.info(
            f"{self.name}: category={category} page={page} "
            f"matches={len(matches)} new={new_count} seen_total={len(seen_ids)}"
        )

        if new_count > 0 and page < MAX_PAGES_PER_CATEGORY:
            base = response.url.split("?")[0]
            yield scrapy.Request(
                f"{base}?page={page + 1}",
                callback=self.parse_category,
                errback=self.errback,
                meta={"category": category, "page": page + 1, "seen_ids": seen_ids},
                dont_filter=True,
            )

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
