"""
Spider for Galmart (Kazakhstan) -- https://galmart.kz/.

Django storefront (csrfmiddlewaretoken in every page + a `sessionid`/
`csrftoken` cookie pair). The category-listing HTML on a plain GET is
mostly template placeholders (`class="product${id}"` -- unrendered
Handlebars-style markup); real product cards only come back from an
XHR-style POST to the SAME url with `X-Requested-With: XMLHttpRequest`,
confirmed live 2026-09-06 via Playwright network-capture, then
reproduced with a bare curl_cffi session (GET once for cookies + the csrf
token, then POST -- no address/city selection needed despite the
GOTCHA note; the leaf category urls already encode a store/department
path and return real products immediately).

  1. GET /catalog/items/1 (or any leaf) for cookies + csrfmiddlewaretoken
     (from the hidden `<input name="csrfmiddlewaretoken" value="...">`).
     The sidebar on ANY catalog page carries the FULL category tree as
     plain `<a href="/catalog/items/{a}/{b}/{c}">` links (383 leaf
     3-segment urls confirmed live 2026-09-06, e.g.
     /catalog/items/1/26/144 "Баранина"/lamb). The first path segment is
     a department id, not a city -- no city/address selection is needed
     for this endpoint despite the CSV's GOTCHA note.
  2. Reuse the SAME csrf token across every leaf's POST (confirmed live
     it is not per-page-bound): POST to the leaf url with
     `ordering=&page=<n>&csrfmiddlewaretoken=<token>`,
     `X-Requested-With: XMLHttpRequest` -> HTTP 201, HTML fragment of
     `<div class="product ... data-id="<id>">...<p class="name">...
     <div class="plus_minus" ... data-price="<kzt>" ...>` blocks.
     Empty body means the page is past the end -- confirmed live
     (page=2/3 both empty on a 10-item leaf).

Confirmed live 2026-09-06: leaf /catalog/items/1/26/144, product 9843
"Полуфабрикат баранины ребра" (lamb ribs) 6,872 KZT (data-price is a
plain decimal-free KZT integer, no minor-unit scaling -- matches
countries.yaml).
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://galmart.kz"
_SEED_URL = f"{_BASE}/catalog/items/1"
_CSRF_RE = re.compile(r'csrfmiddlewaretoken[" ]+value="([^"]+)"')
_LEAF_HREF_RE = re.compile(r'href="(/catalog/items/\d+/\d+/\d+)"')
_PRODUCT_BLOCK_RE = re.compile(
    r'<div class="product[^"]*" data-id="(\d+)">.*?<p class="name">([^<]+)</p>'
    r'.*?data-price="(\d+)"',
    re.S,
)
MAX_PAGES_PER_LEAF = 50


class GalmartKzSpider(scrapy.Spider):
    name = "galmart_kz"
    allowed_domains = ["galmart.kz"]
    currency = "KZT"
    language = "ru"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "COOKIES_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.csrf_token = None

    async def start(self):
        yield scrapy.Request(_SEED_URL, callback=self.parse_seed)

    def parse_seed(self, response):
        m = _CSRF_RE.search(response.text)
        if not m:
            logger.error("galmart_kz: could not find csrfmiddlewaretoken")
            return
        self.csrf_token = m.group(1)
        leaves = sorted(set(_LEAF_HREF_RE.findall(response.text)))
        logger.info(f"galmart_kz: {len(leaves)} leaf categories")
        for leaf in leaves:
            yield self._page_request(leaf, 1)

    def _page_request(self, leaf_path: str, page: int):
        url = f"{_BASE}{leaf_path}"
        return scrapy.Request(
            url,
            method="POST",
            body=f"ordering=&page={page}&csrfmiddlewaretoken={self.csrf_token}",
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Referer": url,
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            },
            callback=self.parse_page,
            meta={"leaf_path": leaf_path, "page": page},
        )

    def parse_page(self, response):
        blocks = _PRODUCT_BLOCK_RE.findall(response.text)
        leaf_path = response.meta["leaf_path"]
        page = response.meta["page"]
        scraped_at = datetime.now(timezone.utc).isoformat()
        for product_id, name, price in blocks:
            item = self._item(product_id, name, price, scraped_at)
            if item:
                yield item
        if blocks and page < MAX_PAGES_PER_LEAF:
            yield self._page_request(leaf_path, page + 1)

    def _item(self, product_id: str, name: str, price: str, scraped_at: str):
        name = name.strip()
        try:
            price_val = float(price)
        except (TypeError, ValueError):
            return None
        if not name or price_val <= 0:
            return None
        return {
            "product_id": product_id,
            "product_name": name[:500],
            "category": None,
            "price": str(price_val),
            "currency": self.currency,
            "available": True,
            "url": f"{_BASE}/catalog/product/{product_id}",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
