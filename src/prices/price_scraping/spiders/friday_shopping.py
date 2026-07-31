import base64
import json
import logging
import time
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_AISEARCH = "https://aisearch-web.shopping.friday.tw/aisearch"
_PRODUCTINFO = (
    "https://frontend-gateway.shopping.friday.tw/frontendapi/product/v3/productinfo"
)
_PAGE_SIZE = 40
_MAX_HITS = 100  # server caps all_cnts at 100 per keyword

_SUPPLIER_FILTER = [
    "",
    "45847,46728,46702,47068,25296,47706,47201,48620,46352,43913,48660,42464,45845,"
    "45982,46139,46200,46664,46201,46252,46287,47978,48107,48252,48248,48287,25036,"
    "45974,46329,46112,46199,47071,48645,48230,45590,23677,44834,43669,46041,46703,"
    "46416,46285,48245,45815,24716,45534,46254,46316,46698,46628,47058,47858,48242,"
    "48557,48748",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
]

_FOOD_KEYWORDS = [
    "米",
    "麵條",
    "咖啡",
    "茶",
    "牛奶",
    "食用油",
    "糖",
    "鹽",
    "醬油",
    "零食",
    "餅乾",
    "巧克力",
    "果汁",
    "礦泉水",
    "啤酒",
    "紅酒",
    "水果",
    "蔬菜",
    "肉",
    "海鮮",
    "雞蛋",
    "麵包",
    "麥片",
    "果醬",
    "蜂蜜",
    "泡麵",
    "罐頭",
    "冷凍食品",
    "調味料",
    "麵粉",
    "堅果",
    "優格",
    "起司",
    "香料",
    "奶粉",
]


class FridayShoppingSpider(scrapy.Spider):
    name = "friday_shopping"
    allowed_domains = ["shopping.friday.tw"]
    currency = "TWD"
    language = "zh"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.4,
        "AUTOTHROTTLE_ENABLED": True,
        "RETRY_TIMES": 5,
        "RETRY_HTTP_CODES": [429, 500, 502, 503, 504, 408],
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "DEFAULT_REQUEST_HEADERS": {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin": "https://ec-w.shopping.friday.tw",
            "Referer": "https://ec-w.shopping.friday.tw/",
        },
    }

    def _target_value(self):
        now = time.time()
        return f"{int(now * 1000) % 10**10}.{int(now)}"

    def _search_request(self, keyword, page):
        body = {
            "remote": "w",
            "sorting": "RELEVANT",
            "and_brand": "",
            "page": page,
            "size": _PAGE_SIZE,
            "filter": {"k": "0100000000", "v": _SUPPLIER_FILTER},
            "limit_cnts": _MAX_HITS,
            "target_value": self._target_value(),
            "kws": keyword,
            "kws64": base64.b64encode(keyword.encode()).decode(),
        }
        return scrapy.Request(
            _AISEARCH,
            method="POST",
            body=json.dumps(body),
            callback=self.parse_search,
            errback=self.errback,
            meta={"keyword": keyword, "page": page},
            dont_filter=True,
        )

    async def start(self):
        for kw in _FOOD_KEYWORDS:
            yield self._search_request(kw, page=1)

    def parse_search(self, response):
        keyword = response.meta["keyword"]
        page = response.meta["page"]
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("friday_shopping: non-JSON aisearch for %s p%d", keyword, page)
            return
        if not payload:
            return
        block = payload[0]
        results = block.get("results") or []
        if not results:
            return

        pids = [r.get("pid") for r in results if r.get("pid")]
        if pids:
            yield self._productinfo_request(pids, keyword)

        all_cnts = block.get("all_cnts") or 0
        if page * _PAGE_SIZE < min(all_cnts, _MAX_HITS):
            yield self._search_request(keyword, page + 1)

    def _productinfo_request(self, pids, keyword):
        body = {"param": {"productIdList": pids, "type": 1, "isPrimary": True}}
        return scrapy.Request(
            _PRODUCTINFO,
            method="POST",
            body=json.dumps(body),
            callback=self.parse_productinfo,
            errback=self.errback,
            meta={"keyword": keyword},
            dont_filter=True,
        )

    def parse_productinfo(self, response):
        keyword = response.meta["keyword"]
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("friday_shopping: non-JSON productinfo for %s", keyword)
            return
        rows = payload.get("resultData") or []
        scraped_at = datetime.now(timezone.utc).isoformat()
        for d in rows:
            price = d.get("bestDiscountPrice")
            if price is None:
                price = d.get("memberPrice")
            if price is None:
                continue
            name = d.get("name")
            if not name:
                continue
            pid = str(d.get("nPid") or d.get("pageId") or "")
            page_id = d.get("pageId")
            yield {
                "product_id": pid,
                "product_name": name.strip(),
                "price": price,
                "currency": self.currency,
                "category": keyword,
                "url": f"https://ec-w.shopping.friday.tw/product/{page_id}"
                if page_id
                else "https://ec-w.shopping.friday.tw/",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

    def errback(self, failure):
        logger.error(
            "friday_shopping: request failed %s — %r",
            failure.request.url,
            failure.value,
        )
