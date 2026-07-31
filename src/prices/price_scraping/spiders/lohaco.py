"""
Spider for LOHACO by ASKUL - https://lohaco.yahoo.co.jp/

A distinct ASKUL retail catalog hosted on a yahoo.co.jp subdomain (its own
/store/h-lohaco/item/{id}/ SKU namespace) — not the general yahoo_shopping
marketplace already covered elsewhere in this repo.

Category landing pages (https://lohaco.yahoo.co.jp/category/{id}/) are
server-rendered (Nuxt SSR) and embed ~80 product cards directly in the HTML
as `<a href="/store/h-lohaco/item/{id}/">` blocks containing a
`v-card__title` name div and a `v-card__text` price div (plain yen amount,
no decoration). No JS rendering needed. The `?page=`/`?p=` query params are
a no-op — every request returns the same ~80-card page, so (like rakuten.py
in this repo) this collects one capped page per category rather than a full
paginated crawl.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)


class LohacoSpider(scrapy.Spider):
    name = "lohaco"
    allowed_domains = ["lohaco.yahoo.co.jp"]
    currency = "JPY"
    language = "ja"

    CATEGORY_IDS = {
        "52494": "コスメ・スキンケア・美容",
        "58068": "食品・調味料・お取り寄せ",
        "58392": "スナック・お菓子",
        "51006": "水・コーヒー・お茶・飲料",
        "58434": "ビール・ワイン・お酒",
        "51710": "洗剤・ティッシュ・日用品",
        "64072": "キッチン・バス・リビング",
        "58435": "ヘアボディ・オーラルケア",
        "52274": "ベビーキッズ・マタニティ",
        "58441": "サプリメント・健康食品",
        "50816": "医薬品・ヘルスケア・介護",
        "61481": "ペット用品",
        "58463": "ファッション",
        "58851": "スポーツ・アウトドア",
        "53421": "文房具・オフィス・手芸",
        "58008": "インテリア・家具・収納",
        "54845": "家電・PC・周辺機器",
        "62290": "カー用品・バイク用品",
    }

    ROW_XPATH = '//a[contains(@href, "/store/") and contains(@href, "/item/")]'
    PRODUCT_ID_RE = re.compile(r"/store/([^/]+)/item/([^/?#]+)")

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 1.5,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
    }

    async def start(self):
        for cat_id, cat_name in self.CATEGORY_IDS.items():
            yield scrapy.Request(
                f"https://lohaco.yahoo.co.jp/category/{cat_id}/",
                callback=self.parse_category,
                meta={"cat_id": cat_id, "cat_name": cat_name},
                errback=self.errback,
            )

    def parse_category(self, response):
        cat_name = response.meta["cat_name"]
        cat_id = response.meta["cat_id"]

        rows = response.xpath(self.ROW_XPATH)
        scraped_at = datetime.now(timezone.utc).isoformat()
        yielded = 0
        seen_ids = set()

        for row in rows:
            item = self._parse_row(row, cat_name, scraped_at, seen_ids)
            if item:
                yielded += 1
                yield item

        logger.info(
            f"lohaco: categoryId={cat_id} ({cat_name}) rows={len(rows)} items={yielded}"
        )

    def _parse_row(self, row, category, scraped_at, seen_ids):
        href = row.xpath("./@href").get()
        if not href:
            return None

        match = self.PRODUCT_ID_RE.search(href)
        product_id = f"{match.group(1)}_{match.group(2)}" if match else None
        dedup_key = product_id or href
        if dedup_key in seen_ids:
            return None
        seen_ids.add(dedup_key)

        name = row.xpath('.//div[contains(@class, "v-card__title")]/text()').get()
        if not name:
            name = row.xpath(".//img/@alt").get()

        price_text = row.xpath('.//div[contains(@class, "v-card__text")]/text()').get()
        price = self._clean_price(price_text)

        if not (name and price):
            return None

        full_url = f"https://lohaco.yahoo.co.jp{href}" if href.startswith("/") else href

        return {
            "product_id": product_id,
            "product_name": name.strip(),
            "category": category,
            "price": price,
            "currency": self.currency,
            "url": full_url,
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }

    def _clean_price(self, price_text):
        if not price_text:
            return None
        match = re.search(r"([\d,]+)", price_text)
        if not match:
            return None
        return match.group(1).replace(",", "")

    def errback(self, failure):
        logger.error(
            f"lohaco request failed: {failure.request.url} — {failure.value!r}"
        )
