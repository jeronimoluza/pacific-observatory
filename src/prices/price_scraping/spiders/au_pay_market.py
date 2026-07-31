"""
Spider for au PAY Market (formerly Wowma!) - https://wowma.jp/

au PAY Market's storefront (wowma.jp) is a client-rendered Next.js app, but the
top-of-page "category ranking" widget it hydrates from is a plain, unauthenticated
JSON API on the api.wowma.net host:

    GET https://api.wowma.net/api/categoryRanking
        ?ref_id=triton_top_ranking_category&period=realtime
        &limit=100&categoryId={id}

A `Referer: https://wowma.jp/` header is required (the API 403s without one);
no cookies/session/auth token are needed. `limit` caps out at 100 items
server-side regardless of the requested value, so each category yields at most
100 ranked products — this is a ranking endpoint, not a full catalog crawl
(same shape as the rakuten.py category-landing-page spider in this repo: one
capped page per category, no deeper pagination exists).

Product URL: https://wowma.jp/item/{seqExhibitId} (confirmed via 308 redirect
from the trailing-slash form). Category IDs + Japanese names were read off
https://wowma.jp/category/list/index.html?spe_id=header_category (a legacy
Shift_JIS-encoded page, still live) via its `cateTitle` / `/category/{id}`
pairs.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)


class AuPayMarketSpider(scrapy.Spider):
    name = "au_pay_market"
    allowed_domains = ["wowma.jp", "api.wowma.net"]
    currency = "JPY"
    language = "ja"

    API_URL = "https://api.wowma.net/api/categoryRanking"
    LIMIT = 100

    CATEGORY_IDS = {
        36: "グルメ・食品",
        48: "ビール・ワイン・お酒",
        57: "水・ソフトドリンク・お茶",
        39: "スイーツ・お菓子",
        35: "キッチン・食器・調理",
        47: "ビューティ・コスメ",
        42: "ダイエット・健康",
        52: "医療・介護・医薬品",
        54: "日用品・文房具・手芸用品",
        34: "キッズベビー・マタニティ",
        51: "レディースファッション",
        50: "メンズファッション",
        53: "家電",
        41: "スマホ・タブレット・モバイル通信",
        31: "インテリア・寝具",
        49: "ペット・ペットグッズ",
        40: "スポーツ・アウトドア",
        59: "花・ガーデン・DIY工具",
        33: "カー用品・バイク用品",
        29: "おもちゃ・趣味",
    }

    HEADERS = {
        "Accept": "application/json",
        "Referer": "https://wowma.jp/",
    }

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 1.5,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
    }

    async def start(self):
        for cat_id, cat_name in self.CATEGORY_IDS.items():
            url = (
                f"{self.API_URL}?ref_id=triton_top_ranking_category"
                f"&period=realtime&limit={self.LIMIT}&categoryId={cat_id}"
            )
            yield scrapy.Request(
                url,
                headers=self.HEADERS,
                callback=self.parse_category,
                meta={"cat_id": cat_id, "cat_name": cat_name},
                errback=self.errback,
                dont_filter=True,
            )

    def parse_category(self, response):
        cat_id = response.meta["cat_id"]
        cat_name = response.meta["cat_name"]

        try:
            items = response.json()
        except ValueError:
            logger.error(f"au_pay_market: JSON decode failed for categoryId={cat_id}")
            return

        if not isinstance(items, list):
            logger.error(
                f"au_pay_market: unexpected payload shape for categoryId={cat_id}"
            )
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        yielded = 0
        for it in items:
            item = self._parse_item(it, cat_name, scraped_at)
            if item:
                yielded += 1
                yield item

        logger.info(
            f"au_pay_market: categoryId={cat_id} ({cat_name}) items={yielded}/{len(items)}"
        )

    def _parse_item(self, it, category, scraped_at):
        exhibit_id = it.get("seqExhibitId")
        name = it.get("itemTitle")
        # usualPrice is sometimes "0" (e.g. certain deal types where the
        # display price lives in ktaiPrice instead) — try both, skip zeros.
        price = self._clean_price(it.get("usualPrice")) or self._clean_price(
            it.get("ktaiPrice")
        )

        if not (exhibit_id and name and price):
            return None

        return {
            "product_id": str(exhibit_id),
            "product_name": name.strip(),
            "category": category,
            "price": price,
            "currency": self.currency,
            "url": f"https://wowma.jp/item/{exhibit_id}",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }

    def _clean_price(self, price_str):
        if not price_str:
            return None
        cleaned = str(price_str).replace(",", "").strip()
        if not cleaned or cleaned == "0":
            return None
        return cleaned

    def errback(self, failure):
        logger.error(
            f"au_pay_market request failed: {failure.request.url} — {failure.value!r}"
        )
