"""
Spider for Rakuten category landing pages - https://www.rakuten.co.jp/category/

Uses scrapy-impersonate with a desktop Safari TLS fingerprint. Chrome/Edge
profiles get HTTP 403 from Rakuten's anti-bot; Safari profiles pass through.
The category landing pages embed ~52 featured products as `div.dui-card`
elements with structured `data-track-*` attributes — no JS rendering needed.
Pagination on the /category/ endpoint is a no-op (every page returns the
same 52 cards) and the /search/mall/-/ endpoint 301s for non-curl clients,
so we collect one page per category.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)


class RakutenSpider(scrapy.Spider):
    name = "rakuten"
    allowed_domains = ["www.rakuten.co.jp"]
    currency = "JPY"
    language = "jp"

    CATEGORY_IDS = [
        ("100227", "食品"),
        ("201184", "米・白米"),
        ("100269", "和風惣菜"),
        ("100275", "洋風惣菜"),
        ("110428", "牛肉"),
        ("200929", "豚肉"),
        ("200939", "鶏肉"),
        ("110411", "カニ"),
        ("207770", "マグロ"),
        ("555086", "レディーストップス"),
        ("555089", "レディースボトムス"),
        ("110765", "メンズトップス"),
        ("558846", "メンズパンツ"),
        ("564497", "ノートPC"),
        ("100026", "デスクトップPC"),
        ("211742", "スマートフォン本体"),
        ("558944", "食器"),
        ("215783", "調理器具"),
        ("100939", "スキンケア"),
        ("100945", "メイクアップ"),
        ("101070", "ランニング"),
        ("101077", "フィットネス"),
    ]

    IMPERSONATE_PROFILE = "safari17_0"

    # Disable project-level RandomBrowserMiddleware and CustomUserAgentMiddleware:
    # both overwrite request state (impersonate profile, UA header), and Rakuten
    # 403s on Chrome TLS fingerprints. Letting curl_cffi's safari profile set its
    # own UA is what passes the anti-bot check.
    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
            "price_scraping.middlewares.CustomUserAgentMiddleware": None,
        },
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scraped_product_ids: set[str] = set()

    def start_requests(self):
        for category_id, category_name in self.CATEGORY_IDS:
            yield scrapy.Request(
                f"https://www.rakuten.co.jp/category/{category_id}/",
                callback=self.parse_category,
                meta={
                    "impersonate": self.IMPERSONATE_PROFILE,
                    "category_id": category_id,
                    "category_name": category_name,
                },
                errback=self.errback,
            )

    def parse_category(self, response):
        category_id = response.meta["category_id"]
        category_name = response.meta["category_name"]

        cards = response.css("div.dui-card[data-track-itemid]")
        items_yielded = 0
        scraped_at = datetime.now(timezone.utc).isoformat()

        for card in cards:
            item_id = card.attrib.get("data-track-itemid")
            price = card.attrib.get("data-track-price")
            name = card.css("img::attr(alt)").get()

            if not (item_id and price and name):
                continue

            product_id = item_id.replace("/", "_")
            if product_id in self.scraped_product_ids:
                continue
            self.scraped_product_ids.add(product_id)

            yield {
                "product_id": product_id,
                "product_name": name.strip()[:500],
                "category": category_name,
                "price": price,
                "currency": self.currency,
                "url": f"https://item.rakuten.co.jp/{item_id}/",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
            items_yielded += 1

        logger.info(
            f"category={category_name} cards={len(cards)} items={items_yielded}"
        )

    def errback(self, failure):
        logger.error(f"Request failed: {failure.request.url} — {failure.value!r}")
