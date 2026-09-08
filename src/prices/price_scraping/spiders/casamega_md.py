"""
Spider for Casa Mega (Moldova) — https://casamega.md/.

CS-Cart storefront (Ultimate 2 / "ut2" theme; `ty-*` classes are CS-Cart's
own Templater/Tygh naming), fully server-rendered. Category listing pages
carry each product's name+link in one anchor
(`<a href="..." class="product-title" title="...">`) followed shortly by
its current price in a `<span class="ty-price-num">N.NN</span>` node --
no JSON-LD or embedded state needed, plain regex-over-HTML suffices (like
zakupy_biedronka_pl.py). Verified live: "Cafea L'OR Espresso Colombia,
capsule, 10 buc" -> MDL 64.05.

Pagination is a plain `/page-N/` path segment, confirmed live (category
`chay-i-kofe/cafea/` links up to `page-7/`). Category discovery: the
homepage's top-nav links to ~17 top-level department paths (mixed
Romanian/Russian slugs, e.g. `/produse-alimentare/...`,
`/krasota-i-zdorove/...`) -- walk each department Home page, and each
one's own `/page-N/` pagination, for a broad partial catalogue rather
than a full category-tree crawl (Casa Mega's nav does not expose the full
subcategory tree in one fetch).
"""

import html as html_module
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_HOME_URL = "https://casamega.md/"
_PRODUCT_RE = re.compile(
    r'href="([^"]+)" class="product-title" title="([^"]+)"'
)
_PRICE_RE = re.compile(r'class="ty-price-num">([\d.]+)<')
_PAGE_LINK_RE = re.compile(r'href="([^"]+/page-\d+/)"')
_NAV_CATEGORY_RE = re.compile(r'href="(/[a-z0-9_\-]+(?:/[a-z0-9_\-]+)*/)"')
_DENY_PREFIXES = ("/digital-card/", "/sale/", "/products-newest/")
MAX_PAGES_PER_CATEGORY = 15


class CasamegaMdSpider(scrapy.Spider):
    name = "casamega_md"
    allowed_domains = ["casamega.md"]
    currency = "MDL"
    language = "ro"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(_HOME_URL, callback=self.parse_home)

    def parse_home(self, response):
        seen = set()
        for href in _NAV_CATEGORY_RE.findall(response.text):
            if href in _DENY_PREFIXES or href in seen:
                continue
            seen.add(href)
            url = urljoin(response.url, href)
            yield scrapy.Request(
                url, callback=self.parse_category, meta={"page": 1}
            )

    def parse_category(self, response):
        yield from self._extract_products(response)

        page = response.meta["page"]
        if page < MAX_PAGES_PER_CATEGORY:
            for href in _PAGE_LINK_RE.findall(response.text):
                url = urljoin(response.url, href)
                next_page = int(re.search(r"page-(\d+)/", url).group(1))
                if next_page == page + 1:
                    yield scrapy.Request(
                        url,
                        callback=self.parse_category,
                        meta={"page": next_page},
                    )
                    break

    def _extract_products(self, response):
        body = response.text
        matches = list(_PRODUCT_RE.finditer(body))
        scraped_at = datetime.now(timezone.utc).isoformat()
        for i, m in enumerate(matches):
            url, name = m.group(1), html_module.unescape(m.group(2))
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else start + 3000
            block = body[start:end]
            price_m = _PRICE_RE.search(block)
            if not name or not price_m:
                continue
            full_url = urljoin(response.url, url)
            category = self._category_from_url(full_url)
            yield {
                "product_id": full_url,
                "product_name": name.strip()[:500],
                "category": category,
                "price": price_m.group(1),
                "currency": self.currency,
                "available": True,
                "url": full_url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

    def _category_from_url(self, url):
        parts = [p for p in url.split("/") if p and "casamega.md" not in p]
        return parts[-2] if len(parts) >= 2 else (parts[0] if parts else None)
