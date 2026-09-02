"""
Spider for LuLu Hypermarket UAE - gcc.luluhypermarket.com (en-ae storefront)

Shared multi-country LuLu GCC storefront (en-ae/en-qa/en-sa/en-om/en-kw/en-bh
locales all live off the same gcc.luluhypermarket.com host per robots.txt --
same platform as the sibling lulu_kw/lulu_om/lulu_bh/lulu_sa spiders). Unlike
those siblings, the en-ae locale runs a newer frontend build: category
listing pages are client-rendered as before, but PDPs no longer carry a
`data-testid="price"` span in the raw HTML (that markup is gone entirely on
this locale -- confirmed absent on multiple PDPs, replaced by `v2-*`
data-testid attributes with no visible price text server-rendered).

However, the page's schema.org Product JSON-LD block -- which is a
permanently-zeroed stub on the sibling GCC locales (offers.price always
"0.00", priceCurrency null, a known defect noted in lulu_sa/_kw/_om/_bh) --
is DIFFERENT on en-ae: for in-stock items it carries the real price and
"aed" as priceCurrency; only genuinely out-of-stock items fall back to the
"0.00"/null stub (confirmed 2026-09-01: 6/25 randomly sampled sitemap URLs
were in-stock with real, distinct AED prices -- e.g. Coca Cola Zero
Calories Can Value Pack 15x155ml at 20.000 AED, Apple iPhone Air 256GB at
4299.000 AED, L'Oreal foundation at 90.000 AED -- while Fage yogurt and a
Barilla pasta SKU sampled from the food keyword list came back "0.00"/None/
InStock=true, i.e. the availability field is NOT reliable and price>0 is
the only trustworthy in-stock signal). So this spider reads JSON-LD
directly instead of a rendered price span. A second JSON-LD BreadcrumbList
node on the same page supplies category (e.g. Grocery > Food Cupboard >
Beverage > Softdrinks & Juices for the Coca-Cola SKU above).

Seeded off /en-ae/sitemap/products-1 (1,980 product URLs at probe time,
single sitemap file, same size as en-sa/en-kw/en-om). Locality proof: "Lulu
UAE" branding in the WebSite JSON-LD node, pz-currency=aed / pz-locale=en-ae
cookies set by the server, VAT tax_rate 5.00 (UAE rate) in the page's
internal product payload, and AED-denominated prices distinct from the
KWD/OMR/BHD/SAR siblings.
"""

import html
import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP_INDEX = "https://gcc.luluhypermarket.com/en-ae/sitemap.xml"
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_JSON_LD_RE = re.compile(
    r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.DOTALL
)
_PID_RE = re.compile(r"/p/([A-Za-z0-9-]+)/?$")


class LuluAeSpider(scrapy.Spider):
    name = "lulu_ae"
    allowed_domains = ["luluhypermarket.com"]
    currency = "AED"
    language = "en"

    custom_settings = {
        # Cloudflare sits in front of gcc.luluhypermarket.com and 403s a
        # plain Scrapy request with no curl_cffi impersonation (same as the
        # sibling lulu_* spiders). Leave the project-default
        # RandomBrowserMiddleware active by not overriding
        # DOWNLOADER_MIDDLEWARES. Kept at 1 request/domain: gcc.
        # luluhypermarket.com is a shared regional platform and sibling
        # country spiders may be scraping the same host concurrently.
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(_SITEMAP_INDEX, callback=self.parse_sitemap_index)

    def parse_sitemap_index(self, response):
        sub_sitemaps = [u for u in _LOC_RE.findall(response.text) if "/products-" in u]
        logger.info("lulu_ae: %d product sitemap files", len(sub_sitemaps))
        for url in sub_sitemaps:
            yield scrapy.Request(url, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        urls = [u for u in _LOC_RE.findall(response.text) if "/p/" in u]
        logger.info("lulu_ae: %d product URLs in %s", len(urls), response.url)
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        product_node = None
        breadcrumb_node = None
        for block in _JSON_LD_RE.findall(response.text):
            try:
                data = json.loads(block)
            except (json.JSONDecodeError, TypeError):
                continue
            node_type = data.get("@type") if isinstance(data, dict) else None
            if node_type == "Product" and product_node is None:
                product_node = data
            elif node_type == "BreadcrumbList" and breadcrumb_node is None:
                breadcrumb_node = data

        if product_node is None:
            return
        offers = product_node.get("offers") or {}
        raw_price = offers.get("price")
        try:
            price = float(raw_price)
        except (TypeError, ValueError):
            return
        if price <= 0:
            return

        name = html.unescape(str(product_node.get("name") or "")).strip()
        if not name:
            return

        sku = product_node.get("sku")
        if sku:
            product_id = str(sku)
        else:
            pid_m = _PID_RE.search(response.url)
            product_id = pid_m.group(1) if pid_m else response.url

        category = None
        if breadcrumb_node:
            names = [
                it.get("name")
                for it in breadcrumb_node.get("itemListElement", [])
                if isinstance(it, dict) and it.get("name")
            ]
            if names:
                category = " > ".join(names)

        yield {
            "product_id": product_id,
            "product_name": name[:500],
            "category": category,
            "price": str(price),
            "currency": self.currency,
            "available": True,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
