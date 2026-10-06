"""
Bibuaran GQ (Equatorial Guinea) -- https://gq.bibuaran.com/. PrestaShop
multi-vendor marketplace (Hostinger hcdn front: chrome124 gets a 6 KB 403,
firefox133 gets 200 -- verified 2026-10-05, so IMPERSONATE_BROWSERS is
pinned to firefox133).

Category listings repeat a "newest" carousel and do not paginate usefully,
so the enumeration surface is the PrestaShop product sitemap
(/sitemap/product/N.xml, ~250 PDP URLs each) and the spider fetches each
PDP. Per-PDP fields: price from <meta property="product:price:amount">
(integer XAF), currency from product:price:currency, name and category
from the breadcrumb (og:title is a "Comprar ... en Guinea" SEO string).
product_id is the numeric prefix of the PDP slug.
"""

import re

import scrapy

_LOC_RE = re.compile(r"<loc>(?:<!\[CDATA\[)?\s*([^<\]]+?)\s*(?:\]\]>)?</loc>")
_PRICE_RE = re.compile(r'<meta property="product:price:amount" content="([\d.]+)"')
_CUR_RE = re.compile(r'<meta property="product:price:currency" content="([A-Z]{3})"')
_CRUMB_RE = re.compile(r'class="breadcrumb">(.*?)</ol>', re.S)
_LI_RE = re.compile(r"<li>(.*?)</li>", re.S)
_TAG_RE = re.compile(r"<[^>]+>")
_ID_RE = re.compile(r"/(\d+)-[^/]+\.html$")


class BibuaranGqSpider(scrapy.Spider):
    name = "bibuaran_gq"
    allowed_domains = ["gq.bibuaran.com"]
    currency = "XAF"
    language = "es"

    custom_settings = {
        "IMPERSONATE_BROWSERS": ["firefox133"],
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
        "RETRY_TIMES": 2,
    }

    async def start(self):
        yield scrapy.Request(
            "https://gq.bibuaran.com/sitemap.xml", callback=self.parse_index
        )

    def parse_index(self, response):
        for loc in _LOC_RE.findall(response.text):
            if "/sitemap/product/" in loc:
                yield scrapy.Request(loc, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        for loc in _LOC_RE.findall(response.text):
            if _ID_RE.search(loc):
                yield scrapy.Request(loc, callback=self.parse_pdp)

    def parse_pdp(self, response):
        text = response.text
        id_m = _ID_RE.search(response.url)
        price_m = _PRICE_RE.search(text)
        crumb_m = _CRUMB_RE.search(text)
        if not (id_m and price_m and crumb_m):
            return
        crumbs = [
            _TAG_RE.sub("", li).strip() for li in _LI_RE.findall(crumb_m.group(1))
        ]
        crumbs = [c for c in crumbs if c]
        if len(crumbs) < 2:
            return
        name = crumbs[-1]
        try:
            price = float(price_m.group(1))
        except ValueError:
            return
        if price <= 0 or not name:
            return
        cur_m = _CUR_RE.search(text)
        yield {
            "product_id": id_m.group(1),
            "product_name": name[:500],
            "category": " > ".join(crumbs[1:-1]) or None,
            "price": str(price),
            "currency": cur_m.group(1) if cur_m else self.currency,
            "available": True,
            "url": response.url,
            "language": self.language,
        }
