"""
Merkado Curacao -- https://merkado.cw/. Next.js classifieds site for Curacao
(cars and real estate, dealers and private sellers; local address in every ad).
Prices are in XCG (Caribbean guilder, the successor to ANG), written
"XCG 139.900,-" with "." thousands separators.

Enumeration: /sitemap.xml lists ~230 /car/<slug> and ~345 /real-estate/<slug>
pages (plus /real-estate/in/<area> and /real-estate/browse index pages, which
are skipped). Each ad page server-renders og:title and og:description; the
description carries the price ("... XCG 52.500,-. Car for sale ..." for cars,
"... For rent . XCG 2.576,- . ..." for real estate). Real-estate rows get the
og:title, which ends in "for rent" or "for sale", so rent and sale prices stay
distinguishable by name. Ads with no price are skipped.
"""

import html
import re

import scrapy

_LOC_RE = re.compile(r"<loc>\s*([^<]+?)\s*</loc>")
_OG_TITLE_RE = re.compile(r'<meta property="og:title" content="([^"]*)"')
_OG_DESC_RE = re.compile(r'<meta property="og:description" content="([^"]*)"')
_PRICE_RE = re.compile(r"\b(?:XCG|ANG)\s*([\d.]+)(?:,(\d{1,2}|-))?")
_AD_RE = re.compile(r"^https://merkado\.cw/(car|real-estate)/([^/?#]+)/?$")


class MerkadoCwSpider(scrapy.Spider):
    name = "merkado_cw"
    allowed_domains = ["merkado.cw"]
    currency = "XCG"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
        "RETRY_TIMES": 2,
    }

    async def start(self):
        yield scrapy.Request("https://merkado.cw/sitemap.xml", callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        for loc in _LOC_RE.findall(response.text):
            m = _AD_RE.match(loc)
            if m and m.group(2) not in ("browse", "in"):
                yield scrapy.Request(loc, callback=self.parse_ad)

    def parse_ad(self, response):
        url_m = _AD_RE.match(response.url)
        text = response.text
        title_m = _OG_TITLE_RE.search(text)
        desc_m = _OG_DESC_RE.search(text)
        if not (url_m and title_m and desc_m):
            return
        price_m = _PRICE_RE.search(html.unescape(desc_m.group(1)))
        if not price_m:
            return
        whole = price_m.group(1).replace(".", "")
        frac = price_m.group(2)
        price = float(whole + ("." + frac if frac and frac.isdigit() else ""))
        name = html.unescape(title_m.group(1)).strip()
        if price <= 0 or not name:
            return
        yield {
            "product_id": url_m.group(2),
            "product_name": name[:500],
            "category": url_m.group(1),
            "price": str(price),
            "currency": self.currency,
            "available": True,
            "url": response.url,
            "language": self.language,
        }
