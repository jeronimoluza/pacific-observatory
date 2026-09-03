"""
Spider for Suning (China) - www.suning.com / search.suning.com.

Two-step scrape, no WAF (confirmed 2026-07-27 probe in
onboard-price-sources/references/known_blockers.md - "the one CN lead
that pans out, overturning China = 0"):

1. Server-rendered search-result HTML (search.suning.com/{keyword}/) yields
   per-card product id + vendor code + name via `li.item-wrap` +
   `input.hidenInfo[vendor]` + `.res-img img[alt]` - no JS execution needed.
2. Price is NOT in the search/PDP HTML; it lives behind a separate JSONP
   microservice keyed by a padded partNumber + vendorCode + a fixed city
   tuple: pas.suning.com/nspcsale_0_{partNumber}_{partNumber}_{vendorCode}_
   180_377_3770100_0_0_0_0_Z001___0_0___.html -> `pcData({...})` with the
   price at data.price.saleInfo[0].netPrice. The "180_377_3770100" city tuple
   (verified against a real captured example URL) and the "Z001" goods-type
   marker are static boilerplate - they work for every product/vendor probed,
   not just self-operated (vendor=0000000000) items. partNumber is simply the
   numeric product id, left-padded to 18 digits.

Seed keywords target COICOP division 01 deep leaves per the onboarding brief:
fresh produce (fruits/vegetables), fish & seafood incl. dried/salted, dairy,
plus the rest of the staple F&B basket. Category is a coarse hint (Suning
doesn't expose a per-card breadcrumb in the list HTML); the downstream Gemini
classifier in src/cpi/coicopping/ does the real COICOP tagging from
product_name.
"""

import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import quote

import scrapy

logger = logging.getLogger(__name__)

_SEARCH_BASE = "https://search.suning.com"
_PRICE_BASE = "https://pas.suning.com"
# Static, product-agnostic tail verified across self-operated (vendor
# 0000000000) and third-party vendor codes alike - see module docstring.
_PRICE_TAIL = "180_377_3770100_0_0_0_0_Z001___0_0___.html"

_JSONP_RE = re.compile(r"^\s*pcData\((.*)\)\s*;?\s*$", re.DOTALL)

# keyword (zh) -> coarse category hint
_SEED_KEYWORDS = {
    # staples
    "大米": "食品/粮油/大米",
    "面条": "食品/粮油/面条",
    "食用油": "食品/粮油/食用油",
    "鸡蛋": "食品/蛋类",
    # meat/poultry
    "猪肉": "食品/肉类/猪肉",
    "牛肉": "食品/肉类/牛肉",
    "鸡肉": "食品/肉类/鸡肉",
    # fish & seafood incl. dried/salted (COICOP 01.1.3)
    "带鱼": "食品/水产/鱼",
    "鱼干": "食品/水产/干货",
    "咸鱼": "食品/水产/腌制",
    "虾": "食品/水产/虾",
    "海鲜": "食品/水产",
    "干贝": "食品/水产/干货",
    # dairy (COICOP 01.1.4)
    "牛奶": "食品/乳品/牛奶",
    "酸奶": "食品/乳品/酸奶",
    "奶酪": "食品/乳品/奶酪",
    "黄油": "食品/乳品/黄油",
    # fresh fruit (COICOP 01.1.6)
    "苹果": "食品/生鲜/水果",
    "香蕉": "食品/生鲜/水果",
    "橙子": "食品/生鲜/水果",
    "西瓜": "食品/生鲜/水果",
    "葡萄": "食品/生鲜/水果",
    # fresh vegetables & tubers (COICOP 01.1.7)
    "白菜": "食品/生鲜/蔬菜",
    "土豆": "食品/生鲜/蔬菜",
    "西红柿": "食品/生鲜/蔬菜",
    "黄瓜": "食品/生鲜/蔬菜",
    "胡萝卜": "食品/生鲜/蔬菜",
    # beverages / other (COICOP 01.2 / 02)
    "茶叶": "食品/饮料/茶",
    "咖啡": "食品/饮料/咖啡",
    "饮料": "食品/饮料",
    "啤酒": "食品/饮料/酒水",
}


class SuningSpider(scrapy.Spider):
    name = "suning"
    allowed_domains = ["search.suning.com", "pas.suning.com"]
    currency = "CNY"
    language = "zh"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        # Plain client negotiates cleanly against these hosts; curl_cffi
        # impersonate has caused SSL/502 rejections on other CN-adjacent
        # hosts in this repo (see waltermart) - keep it off defensively.
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
        },
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
    }

    async def start(self):
        for keyword, category in _SEED_KEYWORDS.items():
            yield scrapy.Request(
                f"{_SEARCH_BASE}/{quote(keyword)}/",
                callback=self.parse_search,
                meta={"keyword": keyword, "category": category},
                headers={"Accept": "text/html"},
            )

    def parse_search(self, response):
        keyword = response.meta["keyword"]
        category = response.meta["category"]
        cards = response.css("li.item-wrap")
        if not cards:
            logger.warning("suning: no product cards for keyword=%s", keyword)
            return
        for card in cards:
            product_id = (card.attrib.get("id") or "").split("-")[-1]
            vendor = card.css("input.hidenInfo::attr(vendor)").get()
            name = card.css(".res-img img::attr(alt)").get()
            if not product_id or not product_id.isdigit() or not vendor or not name:
                continue
            part_number = product_id.zfill(18)
            price_url = f"{_PRICE_BASE}/nspcsale_0_{part_number}_{part_number}_{vendor}_{_PRICE_TAIL}"
            yield scrapy.Request(
                price_url,
                callback=self.parse_price,
                meta={
                    "product_id": product_id,
                    "product_name": name.strip(),
                    "category": category,
                    "url": f"https://product.suning.com/0000000000/{product_id}.html",
                },
                headers={"Accept": "*/*"},
            )

    def parse_price(self, response):
        m = _JSONP_RE.match(response.text)
        if not m:
            logger.warning("suning: unexpected price payload for %s", response.url)
            return
        try:
            payload = json.loads(m.group(1))
        except json.JSONDecodeError:
            logger.warning("suning: non-JSON price payload for %s", response.url)
            return

        sale_info = (payload.get("data", {}).get("price", {}).get("saleInfo") or [{}])[
            0
        ]
        price = (
            sale_info.get("netPrice")
            or sale_info.get("promotionPrice")
            or sale_info.get("originalPrice")
        )
        if not price:
            return
        try:
            float(price)
        except (TypeError, ValueError):
            logger.debug("suning: non-numeric price %r for %s", price, response.url)
            return

        yield {
            "product_id": response.meta["product_id"],
            "product_name": response.meta["product_name"],
            "price": price,
            "currency": self.currency,
            "category": response.meta["category"],
            "url": response.meta["url"],
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
