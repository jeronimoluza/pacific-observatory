"""
NetEase Yanxuan / 网易严选 (China) — https://you.163.com/.

NetEase's own D2C brand. Home goods / apparel / electronics dominate the
overall catalog, but one L1 category — "乳饮酒水" (id 1005002, "dairy /
drinks / wine") — is a genuine narrow food-and-beverage vertical: wine,
baijiu, beer, milk, honey, tea, coffee, juice, cereal.

Probed 2026-09-01. All the obvious CN grocery leaders are already recorded
dead in known_blockers.md (samsclub.cn SPA shell, freshippo/Hema CSR shell,
meituan/pupu CSR shells, jddj, jd.com JDR_shields, yonghui corporate-only).
Yanxuan is the second working CN lead after suning.

Endpoint (Tier 1B, open JSON, no auth, no special headers needed beyond a
real browser TLS fingerprint):

    GET https://you.163.com/xhr/item/listByCategory?categoryId=<id>
    -> {"code": "200", "data": {"category": {...}, "itemList": [...]}}

Only TOP-LEVEL (L1) category ids render server-side; the individual L2 leaf
ids under 1005002 are also directly queryable through this same XHR endpoint
(confirmed — the site's own front-end calls it per-leaf for its category
browse page) and return real per-leaf assortments (4-108 items each), while
the equivalent HTML pages for those same leaf ids serve an empty CSR shell.
Walking the 21 leaf ids gives ~580 distinct SKUs with clean per-leaf category
labels; querying the L1 id (1005002) directly returns a larger, MERGED
~673-distinct-item response but without a reliable per-item category label,
so the leaf walk is used here for label quality even though it costs ~90
fewer rows.

Product URL: https://you.163.com/item/detail?id=<itemId> — confirmed to
render the same name/price server-side.

Prices are in CNY (no symbol on site; site is Chinese-market only, NetEase
is a domestic company — passes the locality bar).
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://you.163.com"

# Leaf categories under L1 "乳饮酒水" (1005002), discovered from the
# server-rendered /item/saleRank?categoryId=1005002 page's subCateList.
CATEGORIES = {
    "1053001": "国产酒",
    "109264007": "名酒馆",
    "109329016": "啤酒",
    "109329017": "牛奶",
    "109342207": "蜂蜜",
    "109206008": "乳品饮料",
    "109329022": "饮料",
    "1005013": "冲调饮品",
    "109333029": "葡萄酒",
    "109333030": "黄酒/洋酒",
    "109333031": "啤酒/果清酒",
    "109333037": "绿茶",
    "109333035": "红茶",
    "109333034": "白茶",
    "109329020": "普洱茶",
    "109333033": "茶叶礼盒",
    "109333042": "果汁",
    "109333044": "咖啡奶茶",
    "109333039": "花茶茶包",
    "109333045": "麦片谷物",
    "109206006": "其它茶类",
}


class NeteaseYanxuanCnSpider(scrapy.Spider):
    name = "netease_yanxuan_cn"
    allowed_domains = ["you.163.com"]
    currency = "CNY"
    language = "zh"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        for cat_id, cat_name in CATEGORIES.items():
            yield scrapy.Request(
                f"{BASE_URL}/xhr/item/listByCategory?categoryId={cat_id}",
                callback=self.parse_category,
                errback=self.errback,
                meta={"cat_id": cat_id, "cat_name": cat_name},
            )

    def parse_category(self, response):
        cat_id = response.meta["cat_id"]
        cat_name = response.meta["cat_name"]
        try:
            payload = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON from {response.url}")
            return

        items = (payload.get("data") or {}).get("itemList") or []
        for item in items:
            item_id = item.get("id")
            name = (item.get("name") or "").strip()
            price = item.get("retailPrice")
            if not item_id or not name or price is None:
                continue
            yield {
                "product_id": str(item_id),
                "product_name": name[:500],
                "category": cat_name,
                "price": str(price),
                "currency": self.currency,
                "available": not (item.get("soldOut") or item.get("underShelf")),
                "url": f"{BASE_URL}/item/detail?id={item_id}",
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        logger.info(f"{self.name}: category={cat_name} ({cat_id}) got={len(items)}")

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
