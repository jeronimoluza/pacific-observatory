"""
Spider for Ochoa (Dominican Republic) -- https://ochoa.com.do/.

Home-improvement / hardware chain. Cloudflare presents a non-blocking JS
challenge snippet; curl_cffi chrome124 clears it and every /productos/
category page renders full server-side HTML (bare curl 403s per the
onboarding probe). Category slugs are discovered once from the homepage nav
(27 live, e.g. /productos/limpieza-16, /productos/ferreteria-8).

Each category paginates via ?pag=N (live-checked 2026-08-17: limpieza-16
pag=1 vs pag=2 return 64 + 64 fully disjoint product ids). Product cards are
<article data-omd_product_listitem="<id>"> blocks; price lives in
p.price > span.offscreen as a plain decimal (RD$ display symbol alongside).
"""

import html
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://ochoa.com.do"
_CATEGORY_RE = re.compile(r'href="(/productos/[a-z0-9-]+)"')
_ARTICLE_START_RE = re.compile(r'<article id="item-')
_ID_RE = re.compile(r'data-omd_product_listitem="(\d+)"')
_NAME_RE = re.compile(r'<h2><a href="([^"]+)" title="([^"]+)">')
_PRICE_RE = re.compile(r'class="price"><span class="offscreen">([\d,]+\.\d+)</span>')
MAX_PAGES = 60


class OchoaDoSpider(scrapy.Spider):
    name = "ochoa_do"
    allowed_domains = ["ochoa.com.do"]
    currency = "DOP"
    language = "es"

    custom_settings = {
        "IMPERSONATE_BROWSERS": ["chrome124"],
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            f"{_BASE}/", callback=self.parse_home, meta={"impersonate": "chrome124"}
        )

    def parse_home(self, response):
        cats = sorted(set(_CATEGORY_RE.findall(response.text)))
        logger.info(f"ochoa_do: {len(cats)} categories discovered")
        for cat in cats:
            yield self._request(cat, 1)

    def _request(self, cat_path: str, page: int):
        return scrapy.Request(
            f"{_BASE}{cat_path}?pag={page}",
            callback=self.parse_category,
            meta={"impersonate": "chrome124", "cat_path": cat_path, "page": page},
        )

    def parse_category(self, response):
        cat_path = response.meta["cat_path"]
        page = response.meta["page"]
        text = response.text
        starts = [m.start() for m in _ARTICLE_START_RE.finditer(text)]
        starts.append(len(text))
        blocks = [text[starts[i] : starts[i + 1]] for i in range(len(starts) - 1)]
        logger.info(f"ochoa_do {cat_path} page={page} cards={len(blocks)}")
        yielded = 0
        for block in blocks:
            item = self._item(block)
            if item:
                yielded += 1
                yield item
        if blocks and page < MAX_PAGES:
            yield self._request(cat_path, page + 1)

    def _item(self, block: str):
        id_m = _ID_RE.search(block)
        name_m = _NAME_RE.search(block)
        price_m = _PRICE_RE.search(block)
        if not (id_m and name_m and price_m):
            return None
        name = html.unescape(name_m.group(2)).strip()
        price = price_m.group(1).replace(",", "")
        if not name or not price:
            return None
        return {
            "product_id": id_m.group(1),
            "product_name": name[:500],
            "category": None,
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": urljoin(_BASE, name_m.group(1)),
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
