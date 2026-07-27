"""
Spider for momo購物網 (Taiwan) - momoshop.com.tw.

momo is a general marketplace, so we seed it with food & beverage search
keywords (COICOP 01 + 02.1). Each search-results page is server-rendered with
a schema.org JSON-LD block whose @graph carries an ItemList of Product objects
(name + offers.price in TWD + product URL) — no JS render or PDP visit needed.
"""

import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import quote

import scrapy

logger = logging.getLogger(__name__)

_SEARCH = "https://www.momoshop.com.tw/search/searchShop.jsp?searchType=1&keyword="

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

_LDJSON_RE = re.compile(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>", re.S)
_ICODE_RE = re.compile(r"i_code=(\d+)")

# momo is a general marketplace: a broad keyword search keeps returning a full
# page of ever-weaker matches indefinitely (relevance-sorted, no natural end).
# Cap pages per keyword to keep the pull bounded and F&B-relevant; the top pages
# hold the real SKUs and the COICOP classifier filters the tail.
_MAX_PAGES = 15


class MomoTwSpider(scrapy.Spider):
    name = "momo_tw"
    allowed_domains = ["momoshop.com.tw"]
    currency = "TWD"
    language = "zh"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.5,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
    }

    async def start(self):
        for kw in _KEYWORDS:
            yield self._page_request(kw, page=1)

    def _page_request(self, kw, page):
        return scrapy.Request(
            f"{_SEARCH}{quote(kw)}&curPage={page}",
            callback=self.parse_search,
            meta={"keyword": kw, "page": page},
        )

    @staticmethod
    def _iter_products(payload):
        """Walk a JSON-LD object graph and yield every Product dict."""
        graph = payload.get("@graph") if isinstance(payload, dict) else None
        nodes = graph if isinstance(graph, list) else [payload]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            for el in node.get("itemListElement") or []:
                item = el.get("item", el) if isinstance(el, dict) else None
                if isinstance(item, dict) and item.get("@type") == "Product":
                    yield item

    def parse_search(self, response):
        kw = response.meta["keyword"]
        page = response.meta["page"]
        found = 0
        scraped_at = datetime.now(timezone.utc).isoformat()
        for block in _LDJSON_RE.findall(response.text):
            try:
                payload = json.loads(block.strip())
            except json.JSONDecodeError:
                continue
            for prod in self._iter_products(payload):
                name = prod.get("name")
                offers = prod.get("offers") or {}
                price = offers.get("price") if isinstance(offers, dict) else None
                url = prod.get("url")
                if not name or price is None or not url:
                    continue
                m = _ICODE_RE.search(url)
                found += 1
                yield {
                    "product_id": m.group(1) if m else None,
                    "product_name": name,
                    "price": price,
                    "currency": self.currency,
                    "category": kw,
                    "url": url,
                    "language": self.language,
                    "scraped_at_utc": scraped_at,
                }
        logger.info("momo_tw: keyword=%s page=%d products=%d", kw, page, found)
        # Paginate until an empty page or the relevance cap, whichever comes first.
        if found and page < _MAX_PAGES:
            yield self._page_request(kw, page + 1)

    def errback(self, failure):
        logger.error(
            "momo_tw: request failed %s — %r", failure.request.url, failure.value
        )
