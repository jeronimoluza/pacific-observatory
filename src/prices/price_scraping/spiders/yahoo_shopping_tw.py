"""
Spider for Yahoo!奇摩購物中心 (Yahoo Shopping Taiwan) — tw.buy.yahoo.com.

Distinct Taiwan-market Yahoo property (yahoo.com.tw / Yahoo Kimo), unrelated
to the already-covered Japan yahoo_shopping spider.

The site is a general marketplace, so we seed it with food & beverage search
keywords (COICOP 01 + 02.1), same pattern as momo_tw. Each search-results
page (`/search/product?p={kw}&pg={n}`) is server-rendered with a
`<script id="isoredux-data">` block whose Redux state carries
`search.ecsearch.hits` — 60 products/page with name, price (TWD), product id,
category, and canonical URL. No auth or JS render needed.
"""

import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import quote

import scrapy

logger = logging.getLogger(__name__)

_SEARCH = "https://tw.buy.yahoo.com/search/product?p={kw}&pg={page}"

# Food & beverage seed terms: milk, bread, rice, eggs, cooking oil, coffee, tea,
# juice, mineral water, instant noodles, biscuits, soy sauce, sugar, salt,
# beer, wine (02.1).
_KEYWORDS = [
    "牛奶",
    "麵包",
    "白米",
    "雞蛋",
    "食用油",
    "咖啡",
    "茶包",
    "果汁",
    "礦泉水",
    "泡麵",
    "餅乾",
    "醬油",
    "砂糖",
    "鹽",
    "啤酒",
    "紅酒",
]

_ISOREDUX_RE = re.compile(r'<script id="isoredux-data"[^>]*>(.*?)</script>', re.S)

# Marketplace search is relevance-sorted with no natural end; cap pages per
# keyword to keep the pull bounded (60 items/page).
_MAX_PAGES = 15


class YahooShoppingTwSpider(scrapy.Spider):
    name = "yahoo_shopping_tw"
    allowed_domains = ["tw.buy.yahoo.com"]
    currency = "TWD"
    language = "zh"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 2.5,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429, 403],
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scraped_ids = set()

    async def start(self):
        for kw in _KEYWORDS:
            yield self._page_request(kw, page=1)

    def _page_request(self, kw, page):
        return scrapy.Request(
            _SEARCH.format(kw=quote(kw), page=page),
            callback=self.parse_search,
            meta={"keyword": kw, "page": page},
            errback=self.errback,
        )

    def parse_search(self, response):
        kw = response.meta["keyword"]
        page = response.meta["page"]

        match = _ISOREDUX_RE.search(response.text)
        if not match:
            logger.warning(
                f"yahoo_shopping_tw: no isoredux-data block, kw={kw} page={page}"
            )
            return

        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            logger.warning(
                f"yahoo_shopping_tw: unparseable isoredux JSON, kw={kw} page={page}"
            )
            return

        hits = (data.get("search") or {}).get("ecsearch", {}).get("hits") or []
        found = 0
        scraped_at = datetime.now(timezone.utc).isoformat()
        for hit in hits:
            pres = hit.get("pres_data") or {}
            product_id = hit.get("ec_productno")
            name = pres.get("productname_disp")
            price = hit.get("ec_price")
            url = pres.get("producturl")
            if not (product_id and name and price and url):
                continue
            if product_id in self.scraped_ids:
                continue
            self.scraped_ids.add(product_id)
            found += 1
            yield {
                "product_id": str(product_id),
                "product_name": name.strip(),
                "brand": hit.get("ec_brand") or None,
                "category": pres.get("subcatname") or kw,
                "price": str(price),
                "currency": self.currency,
                "url": url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        logger.info(
            f"yahoo_shopping_tw: kw={kw} page={page} hits={len(hits)} new={found}"
        )
        if found and page < _MAX_PAGES:
            yield self._page_request(kw, page + 1)

    def errback(self, failure):
        logger.error(
            f"yahoo_shopping_tw: request failed {failure.request.url} — {failure.value!r}"
        )
