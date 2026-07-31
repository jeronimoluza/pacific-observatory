"""
Spider for Alibaba Health Pharmacy (China) - www.liangxinyao.com / 阿里健康大药房.

The storefront is a Tmall shop (maiyao.liangxinyao.com). The PC home page at
www.liangxinyao.com is GBK-encoded and server-renders the shop's full category
tree as `category-<catId>.htm` links (with the GBK-percent-encoded `catName`
in the query string). Each category's products are NOT in the category HTML -
they load from the shop's async search module:

  //maiyao.liangxinyao.com/i/asynSearch.htm?mid=w-<WID>-0&wid=<WID>
      &path=/category.htm&search=y&catId=<catId>&pageNo=<n>

The widget id `15101647109` is the shop's search-result module and is constant
across every category (verified 2026-07-31 across catIds 1250010419 /
1276249451 / 1276255131). The endpoint returns a GBK JS-string HTML fragment
(document.write payload, so `"` are backslash-escaped) carrying up to ~60 items
per page: `dl.item[data-id]` + `.item-name` anchor + `.c-price`. Product id is
the Tmall item id; the canonical PDP is detail.tmall.com/item.htm?id=<id>.

Prices are CNY (¥). category is the decoded shop catName - a coarse hint;
real COICOP tagging is deferred to src/cpi/coicopping/. curl_cffi impersonate
is left off (plain client negotiates cleanly; impersonate has caused SSL/502
rejections on other CN hosts in this repo).
"""

import logging
import re
from datetime import datetime, timezone
from urllib.parse import unquote_to_bytes

import scrapy

logger = logging.getLogger(__name__)

_HOME = "https://www.liangxinyao.com/"
_ASYN = "https://maiyao.liangxinyao.com/i/asynSearch.htm"
_WID = "15101647109"
_MAX_PAGES = 40

_CAT_RE = re.compile(r"category-(\d+)\.htm\?[^\"']*?catName=([^&\"']+)")
_ITEM_SPLIT_RE = re.compile(r'(?=<dl class="item)')
_ID_RE = re.compile(r'data-id="(\d+)"')
_NAME_RE = re.compile(r'class="item-name[^"]*"[^>]*>(.*?)</a>', re.DOTALL)
_PRICE_RE = re.compile(r'class="c-price"[^>]*>(.*?)</', re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")


def _decode(body):
    text = body.decode("gbk", errors="ignore")
    return text.replace('\\"', '"').replace("\\'", "'").replace("\\/", "/")


def _clean(fragment):
    return _TAG_RE.sub("", fragment).strip()


class AlibabaHealthPharmacySpider(scrapy.Spider):
    name = "alibaba_health_pharmacy"
    allowed_domains = ["liangxinyao.com"]
    start_urls = [_HOME]
    currency = "CNY"
    language = "zh"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
        },
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
    }

    def _asyn_url(self, cat_id, page_no):
        return (
            f"{_ASYN}?mid=w-{_WID}-0&wid={_WID}&path=/category.htm"
            f"&search=y&catId={cat_id}&pageNo={page_no}"
        )

    def parse(self, response):
        text = _decode(response.body)
        cats = {}
        for cat_id, raw_name in _CAT_RE.findall(text):
            if cat_id in cats:
                continue
            try:
                cats[cat_id] = unquote_to_bytes(raw_name).decode("gbk")
            except UnicodeDecodeError:
                cats[cat_id] = None
        logger.info("alibaba_health_pharmacy: %d categories discovered", len(cats))
        for cat_id, cat_name in cats.items():
            yield scrapy.Request(
                self._asyn_url(cat_id, 1),
                callback=self.parse_category,
                meta={"cat_id": cat_id, "category": cat_name, "page": 1},
                headers={
                    "Referer": f"https://maiyao.liangxinyao.com/category-{cat_id}.htm?search=y",
                    "X-Requested-With": "XMLHttpRequest",
                },
            )

    def parse_category(self, response):
        cat_id = response.meta["cat_id"]
        category = response.meta["category"]
        page = response.meta["page"]

        text = _decode(response.body)
        count = 0
        for block in _ITEM_SPLIT_RE.split(text):
            id_m = _ID_RE.search(block)
            name_m = _NAME_RE.search(block)
            price_m = _PRICE_RE.search(block)
            if not (id_m and name_m and price_m):
                continue
            name = _clean(name_m.group(1))
            price = _clean(price_m.group(1))
            product_id = id_m.group(1)
            if not name or not price:
                continue
            count += 1
            yield {
                "product_id": product_id,
                "product_name": name,
                "price": price,
                "currency": self.currency,
                "category": category,
                "url": f"https://detail.tmall.com/item.htm?id={product_id}",
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        if count > 0 and page < _MAX_PAGES:
            next_page = page + 1
            yield scrapy.Request(
                self._asyn_url(cat_id, next_page),
                callback=self.parse_category,
                meta={"cat_id": cat_id, "category": category, "page": next_page},
                headers={
                    "Referer": f"https://maiyao.liangxinyao.com/category-{cat_id}.htm?search=y",
                    "X-Requested-With": "XMLHttpRequest",
                },
            )
