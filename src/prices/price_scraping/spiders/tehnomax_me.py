"""
Spider for Tehnomax (Montenegro) -- https://www.tehnomax.me/.

Custom PHP storefront behind Cloudflare (bare requests 403 "cf-mitigated:
challenge"; curl_cffi impersonate=chrome124 clears both homepage and
category pages cleanly, verified live 2026-08-17).

Category discovery: the site's sitemap.xml (11.4k <loc> entries) filtered
to the 472 two-segment category paths (e.g. tv-audio-video/auto-radio);
three-segment entries in the same sitemap are individual product pages.
Pagination is a path-segment page number (.../<cat>/<sub>/<page>), proven
live: /bijela-tehnika/frizideri (page 1, implicit) vs
/bijela-tehnika/frizideri/2 return 60 + 60 product ids (from the
`fnc-product-name-<id>` markup), zero overlap; the listing itself reports
"Prikaz 1 - 60 od 255" so most categories span several pages.

Product blocks are delimited by `product-wrap-grid js-product-ga-wrap`;
name+id come from `id="fnc-product-name-<id>">NAME</div>`, price from the
first `class="price">AMOUNT €</div>` in the block (a second, unrelated
"RATA OD X €" -- monthly installment -- span follows later in the same
block and must not be matched first).
"""

import html
import re
from datetime import datetime, timezone

import scrapy

logger_name = __name__

_BASE = "https://www.tehnomax.me"
_LOC_RE = re.compile(r"<loc>(https://tehnomax\.me/[a-z0-9\-]+/[a-z0-9\-]+)</loc>")
_SPLIT_MARKER = "product-wrap-grid js-product-ga-wrap"
_ID_RE = re.compile(r'id="fnc-product-name-(\d+)"')
_NAME_RE = re.compile(r'id="fnc-product-name-\d+">\s*([^<]+?)\s*</div>')
_URL_RE = re.compile(r'<a class="product-link" href="([^"]+)"')
_PRICE_RE = re.compile(r'class="price">\s*([\d.,]+)\s*€')
_MAX_PAGES = 30


class TehnomaxMeSpider(scrapy.Spider):
    name = "tehnomax_me"
    allowed_domains = ["tehnomax.me"]
    currency = "EUR"
    language = "sr"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
        },
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }
    IMPERSONATE_PROFILE = "chrome124"

    async def start(self):
        yield scrapy.Request(
            "https://www.tehnomax.me/sitemap.xml",
            callback=self.parse_discovery,
            meta={"impersonate": self.IMPERSONATE_PROFILE},
        )

    def parse_discovery(self, response):
        urls = sorted(set(_LOC_RE.findall(response.text)))
        for u in urls:
            cat_url = u.replace("https://tehnomax.me/", f"{_BASE}/")
            yield scrapy.Request(
                cat_url,
                callback=self.parse_listing,
                meta={
                    "page": 1,
                    "base": cat_url,
                    "impersonate": self.IMPERSONATE_PROFILE,
                },
            )

    def parse_listing(self, response):
        body = response.text
        page = response.meta["page"]
        base = response.meta["base"]
        category = base.rstrip("/").split("tehnomax.me/", 1)[-1]
        blocks = body.split(_SPLIT_MARKER)[1:]
        found = 0
        for b in blocks:
            item = self._item(b, category)
            if item:
                found += 1
                yield item
        if found and page < _MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{base}/{nxt}",
                callback=self.parse_listing,
                meta={
                    "page": nxt,
                    "base": base,
                    "impersonate": self.IMPERSONATE_PROFILE,
                },
            )

    def _item(self, block: str, category: str):
        id_match = _ID_RE.search(block)
        name_match = _NAME_RE.search(block)
        url_match = _URL_RE.search(block)
        price_match = _PRICE_RE.search(block)
        if not (id_match and name_match and price_match):
            return None
        price = (
            price_match.group(1).replace("\xa0", "").replace(".", "").replace(",", ".")
        )
        return {
            "product_id": id_match.group(1),
            "product_name": html.unescape(name_match.group(1))[:500],
            "category": category,
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": url_match.group(1) if url_match else "",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
