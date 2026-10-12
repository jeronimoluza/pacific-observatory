"""
Mercado Semu GQ (Equatorial Guinea) -- https://mercadosemu.com/. Next.js
user-classifieds marketplace ("el marketplace de Guinea Ecuatorial"), listings
in Malabo, Bata and the other provinces, prices in FCFA (XAF, integer, written
with "." thousands separators: 3.000.000 FCFA).

Enumeration: /sitemap.xml lists every /listing/<uuid> page (~110). Each listing
page is server-rendered metadata: <meta property="og:title"> is
"<title> -- <price> FCFA" and og:description is "<price> FCFA . <title> en
<city>. <free text>". The item category is the ?cat=<slug> link on the page.
Listings with price 0 (price on request) are skipped.
"""

import html
import re

import scrapy

_LOC_RE = re.compile(r"<loc>\s*([^<]+?)\s*</loc>")
_OG_TITLE_RE = re.compile(r'<meta property="og:title" content="([^"]*)"')
_OG_DESC_RE = re.compile(r'<meta property="og:description" content="([^"]*)"')
_PRICE_TAIL_RE = re.compile(r"\s+—\s+([\d.,]+)\s*FCFA\s*$")
_CITY_RE = re.compile(r"\sen\s+([^.]+?)\.(?:\s|$)")
_CAT_RE = re.compile(r"\?cat=([a-z0-9_-]+)")
_ID_RE = re.compile(r"/listing/([0-9a-f-]{36})")


class MercadosemuGqSpider(scrapy.Spider):
    name = "mercadosemu_gq"
    allowed_domains = ["mercadosemu.com"]
    currency = "XAF"
    language = "es"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
        "RETRY_TIMES": 2,
    }

    async def start(self):
        yield scrapy.Request(
            "https://mercadosemu.com/sitemap.xml", callback=self.parse_sitemap
        )

    def parse_sitemap(self, response):
        for loc in _LOC_RE.findall(response.text):
            if _ID_RE.search(loc):
                yield scrapy.Request(loc, callback=self.parse_pdp)

    def parse_pdp(self, response):
        text = response.text
        id_m = _ID_RE.search(response.url)
        title_m = _OG_TITLE_RE.search(text)
        if not (id_m and title_m):
            return
        title = html.unescape(title_m.group(1)).strip()
        price_m = _PRICE_TAIL_RE.search(title)
        if not price_m:
            return
        name = _PRICE_TAIL_RE.sub("", title).strip()
        try:
            price = float(re.sub(r"[.,]", "", price_m.group(1)))
        except ValueError:
            return
        if price <= 0 or not name:
            return
        cat_m = _CAT_RE.search(text)
        yield {
            "product_id": id_m.group(1),
            "product_name": name[:500],
            "category": cat_m.group(1) if cat_m else None,
            "price": str(price),
            "currency": self.currency,
            "available": True,
            "url": response.url,
            "language": self.language,
        }
