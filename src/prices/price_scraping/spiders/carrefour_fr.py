"""
Carrefour France (hypermarket) -- https://www.carrefour.fr/.

Salesforce-style enterprise storefront behind Cloudflare. The default
repo-pinned curl_cffi profile (settings.py IMPERSONATE_BROWSERS=chrome120)
403s on this tenant, as do chrome124 and chrome131. `safari17_0` and
`firefox133` both clear at 200 (verified 2026-09-06) -- this spider pins
`IMPERSONATE_BROWSERS` to safari17_0 accordingly.

Category rayons pages (`/r/<slug>`) are server-rendered HTML, one
`<article data-testId="<ean>" class="product-list-card-plp-grid">` block
per product tile, each carrying:
  - price:   <p class="product-list-card-plp-grid__shimmer-base-price">
             "1,65<span ...>€</span>"
  - title:   <h3 id="product-card-title">...</h3>
  - href:    <a data-testid="product-card-title" href="/p/<slug>-<ean>">
  - pack:    <p class="product-list-card-plp-grid__packaging">"1,25L"</p>

Verified live 2026-09-06: /r/boissons page 1 vs page 2 (`?page=N`) return
disjoint sets of 28-30 product titles each -- genuine pagination, not a
homepage-carousel trap. auchan.fr and monoprix.fr on the same probe pass
either hide price behind a client-side "show price" click (auchan) or
gate the SPA's API behind an AWS WAF captcha (monoprix) -- carrefour.fr is
the one of the three French hypermarket giants whose price is in the raw
HTML with no further gate.

A CrawlSpider follows every `/r/` rayon link (category tree) plus
`?page=N` pagination links found on rayon pages themselves.

`data-testId` on the article is the EAN/product id used to build the
canonical `/p/<slug>-<id>` URL, so `product_id` is exact.
"""

import logging
import re

import scrapy
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule

logger = logging.getLogger(__name__)

_ARTICLE_RE = re.compile(
    r'<article data-testId="(?P<id>\d+)"[^>]*class="product-list-card-plp-grid">'
    r"(?P<body>.*?)</article>",
    re.S,
)
_PRICE_RE = re.compile(
    r'product-list-card-plp-grid__shimmer-base-price">\s*([\d,]+)\s*<span[^>]*>\s*€',
    re.S,
)
_TITLE_RE = re.compile(
    r'<h3 id="product-card-title"[^>]*>\s*([^<]+?)\s*</h3>', re.S
)
_HREF_RE = re.compile(r'<a data-testid="product-card-title" href="([^"]+)"')


class CarrefourFrSpider(CrawlSpider):
    name = "carrefour_fr"
    allowed_domains = ["carrefour.fr"]
    start_urls = ["https://www.carrefour.fr/"]
    currency = "EUR"
    language = "fr"

    custom_settings = {
        "IMPERSONATE_BROWSERS": ["safari17_0"],
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
        "DEPTH_LIMIT": 4,
        "DOWNLOAD_TIMEOUT": 60,
    }

    rules = (
        Rule(
            LinkExtractor(allow=r"/r/[^?]+(\?page=\d+)?$"),
            callback="parse_category",
            follow=True,
        ),
    )

    def parse_category(self, response):
        found = 0
        for m in _ARTICLE_RE.finditer(response.text):
            item = self._item(m)
            if item:
                found += 1
                yield item
        logger.info(f"{self.name}: {response.url} tiles_yielded={found}")

    def _item(self, match):
        pid = match.group("id")
        body = match.group("body")

        price_m = _PRICE_RE.search(body)
        title_m = _TITLE_RE.search(body)
        href_m = _HREF_RE.search(body)
        if not (price_m and title_m):
            return None

        try:
            price = float(price_m.group(1).replace(",", "."))
        except ValueError:
            return None
        if price <= 0:
            return None

        title = title_m.group(1).strip()
        if not title:
            return None

        url = (
            "https://www.carrefour.fr" + href_m.group(1)
            if href_m
            else f"https://www.carrefour.fr/p/{pid}"
        )

        return {
            "product_id": pid,
            "product_name": title[:500],
            "price": str(price),
            "currency": self.currency,
            "category": None,
            "url": url,
            "available": True,
            "language": self.language,
        }
