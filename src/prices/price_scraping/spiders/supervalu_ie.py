"""
Spider for SuperValu Ireland -- https://shop.supervalu.ie/, the chain's own
online storefront (Mi9 Retail Cloud platform, `mi9-storefront` root div).

Not the same source as the existing `quidu_ie` config: quidu.ie is a
third-party price-comparison aggregator that republishes a partial,
keyword-search-seeded slice of SuperValu/Aldi/Dunnes/Tesco SKUs it scraped
itself. This spider walks shop.supervalu.ie's own catalog directly via its
sitemap, so it is additive rather than a duplicate.

Product-detail pages are server-rendered (no JS needed, no Googlebot UA
trick required) and carry Schema.org data as `<meta itemprop="...">` tags
rather than JSON-LD -- confirmed live 2026-09-10:
  <meta itemprop="name" content="Nestle Kit Kat Cereal  (330 g)" />
  <meta itemprop="price" content="€3.00" />
  <meta itemprop="currency" content="EUR" />
  <meta itemprop="sku" content="1884136000" />
An OpenGraph `og:title`/`og:url` pair duplicates name/url on the same page,
so the pipeline's shared `row_from_meta` fallback (built for exactly this
itemprop/OpenGraph shape) parses it directly with no new regex; the only
gap is `sku`, which `row_from_meta` doesn't read, pulled here separately.

/sitemap.xml is a single flat <urlset> (not a <sitemapindex>) mixing
categories, promotions, recipes and products -- 13,670 <loc> entries total,
11,807 of which match `/product/<slug>-id-<digits>`.  Sampled 7 product
URLs spread across the full range (positions 0, 500, 3000, 6000, 7500,
9000, 11800): 5 returned a real name + non-zero EUR price (1.89 to 10.00),
2 were zero-price/no-name stubs for discontinued items -- dropped, per the
zero-price rule, by simply yielding nothing when `row_from_meta` returns
None.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

from ..archived import meta_tags, row_from_meta

logger = logging.getLogger(__name__)

_SITEMAP_URL = "https://shop.supervalu.ie/sitemap.xml"
_PRODUCT_RE = re.compile(r"/product/")


class SupervaluIeSpider(scrapy.Spider):
    name = "supervalu_ie"
    allowed_domains = ["shop.supervalu.ie"]
    currency = "EUR"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(_SITEMAP_URL, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        urls = response.xpath("//*[local-name()='loc']/text()").getall()
        product_urls = [u for u in urls if _PRODUCT_RE.search(u)]
        logger.info(
            f"supervalu_ie: sitemap has {len(urls)} urls, "
            f"{len(product_urls)} products"
        )
        for url in product_urls:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        row = row_from_meta(response.text, response.url)
        if row is None:
            return
        sku = meta_tags(response.text).get("sku")
        if sku:
            row["product_id"] = str(sku)
        row.setdefault("currency", self.currency)
        row["language"] = self.language
        row["scraped_at_utc"] = datetime.now(timezone.utc).isoformat()
        yield row

    @classmethod
    def parse_html(cls, html_text: str, url: str):
        """Parse one archived SuperValu IE PDP page. Same meta-tag path
        as the live crawl."""
        row = row_from_meta(html_text, url)
        if row is None:
            return
        sku = meta_tags(html_text).get("sku")
        if sku:
            row["product_id"] = str(sku)
        row.setdefault("currency", cls.currency)
        row["language"] = cls.language
        yield row
