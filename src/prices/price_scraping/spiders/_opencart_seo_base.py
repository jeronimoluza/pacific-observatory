"""
OpenCart clean-SEO storefronts with no `route=`/`path=` in the URLs.

Categories and products share the same shape (`/<slug>` or `/<parent>/<child>`),
so there is no URL pattern that tells them apart. This base walks every
same-host link of at most `MAX_SEGMENTS` path segments found on `NAV_URL`, parses `div.product-thumb` / `div.product-layout` cards
with the stock `OpencartBaseSpider._item`, and follows `?page=N` only while a
page still yields cards. A product page yields no cards, so it costs one
request and nothing else. `product_id` falls back to the URL slug in the parent
(no numeric id exists), and `DEDUPE_PRODUCT_IDS` keeps a product that is listed
under several categories to one row.

Underscored filename -- Scrapy's SpiderLoader skips classes without `name`.
"""

import re
from urllib.parse import urljoin, urlsplit

import scrapy

from price_scraping.spiders._opencart_base import OpencartBaseSpider

_HREF_RE = re.compile(r'href="([^"#]+)"')
_SKIP_RE = re.compile(
    r"(cuenta|account|login|registro|cart|carrito|checkout|contact|aviso|legal|"
    r"privacy|privacidad|politica|cookie|condicion|envios|devolucion|pago|payment|"
    r"blog|wishlist|lista-de-deseos|mapa|sitemap|about|nosotros|search|buscar|"
    r"image/|catalog/|\.(?:css|js|png|jpe?g|gif|svg|webp|ico|pdf|xml|php)$)",
    re.IGNORECASE,
)


class OpencartSeoWalkSpider(OpencartBaseSpider):
    DEDUPE_PRODUCT_IDS = True
    MAX_SEGMENTS = 2
    # optional path prefix (e.g. "/en") that every followed link must carry
    LANG_PREFIX = ""

    async def start(self):
        yield scrapy.Request(self.NAV_URL, callback=self.parse_nav)

    def _internal_links(self, response):
        host = urlsplit(self.NAV_URL).netloc.removeprefix("www.")
        for href in _HREF_RE.findall(response.text):
            url = urljoin(response.url, href.replace("&amp;", "&"))
            parts = urlsplit(url)
            if parts.netloc.removeprefix("www.") != host or parts.query:
                continue
            path = parts.path.rstrip("/")
            if self.LANG_PREFIX and not path.startswith(self.LANG_PREFIX + "/"):
                continue
            segs = [s for s in path[len(self.LANG_PREFIX) :].split("/") if s]
            if not segs or len(segs) > self.MAX_SEGMENTS or _SKIP_RE.search(path):
                continue
            yield f"{parts.scheme}://{parts.netloc}{path}"

    def parse_nav(self, response):
        # menu links on the home page only: the mega-menu already lists the whole
        # category tree, and following links off product pages would crawl the
        # catalogue one PDP at a time
        for url in sorted(set(self._internal_links(response))):
            yield scrapy.Request(
                url, callback=self.parse_category, meta={"page": 1, "cat_url": url}
            )
