"""
Spider for Paykar Shop (Tajikistan) — https://paykar.shop/.

Server-rendered Bitrix (1C-Bitrix) storefront in Dushanbe. The 24 top-level
categories at /catalog/<slug>/ each render their own product grid directly
(not just subcategory links) with Bitrix pagination via ?PAGEN_1=N. Re-
verified live 2026-08-06: /catalog/bakaleya/gotovye_zavtraki_kashi_khlopya/137220/
-> 200, h1 'Хлопья овсяные РП 500г Геркулес монастырский'; the parent
category page /catalog/bakaleya/ -> 200, 21 product cards per page with
data-id + data-currency="TJS" data-value="21.2" pricing attributes, prices
already in whole somoni (no minor-unit scaling needed, matches shard
currency TJS == cfg_currency TJS).

Pagination: requesting a page past the last one silently falls back to
page 1 content (identical data-id set), so each category's crawl stops
either on an empty page or when the returned product id set matches
page 1's (detects the fallback rather than relying on a fixed page size).
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE = "https://paykar.shop"
TOP_CATEGORIES = [
    "bakaleya",
    "chay_kofe_kakao",
    "dlya_zhivotnykh",
    "frukty_i_ovoshchi",
    "gotovaya_eda",
    "kantselyarskie_i_ofisnye_prinadlezhnosti",
    "khlebobulochnye_izdeliya",
    "konditerskie_izdeliya",
    "konservirovannye_produkty",
    "krasota_i_gigiena",
    "molochnye_produkty",
    "myasnaya_gastronomiya",
    "myaso_ptitsa",
    "nasha_pekarnya",
    "novye_tovary",
    "odezhda",
    "parfyum",
    "polufabrikaty_moreprodukty",
    "sladosti",
    "sneki",
    "sousy_zapravki",
    "tovary_dlya_doma_i_otdykha",
    "voda_i_napitki",
    "vse_dlya_detey",
    "zdorovoe_pitanie",
]
MAX_PAGES = 60  # safety cap per category

_ITEM_RE = re.compile(
    r'data-id="(\d+)"\s+data-product_type="1">'
    r'(?P<body>.*?)(?=data-id="\d+"\s+data-product_type="1">|\Z)',
    re.S,
)
_TITLE_RE = re.compile(r'class="dark_link[^"]*"><span[^>]*>([^<]+)</span>')
_PRICE_RE = re.compile(r'data-currency="([A-Z]{3})"\s+data-value="([\d.]+)"')


class PaykarTjSpider(scrapy.Spider):
    name = "paykar_tj"
    allowed_domains = ["paykar.shop"]
    currency = "TJS"
    language = "ru"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        for slug in TOP_CATEGORIES:
            yield scrapy.Request(
                f"{BASE}/catalog/{slug}/",
                callback=self.parse_page,
                meta={"category": slug, "page": 1, "first_page_ids": None},
            )

    def parse_page(self, response):
        category = response.meta["category"]
        page = response.meta["page"]
        blocks = list(_ITEM_RE.finditer(response.text))
        ids = [m.group(1) for m in blocks]
        if not ids:
            return

        first_page_ids = response.meta["first_page_ids"]
        if page > 1 and ids == first_page_ids:
            # Bitrix silently serves page 1 again once we're past the last page.
            return

        logger.info(f"paykar_tj: {category} page={page} items={len(ids)}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for m in blocks:
            item = self._item(m, category, response.url, scraped_at)
            if item:
                yield item

        if page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{BASE}/catalog/{category}/?PAGEN_1={nxt}",
                callback=self.parse_page,
                meta={
                    "category": category,
                    "page": nxt,
                    "first_page_ids": ids if page == 1 else first_page_ids,
                },
            )

    def _item(self, m: re.Match, category: str, page_url: str, scraped_at: str):
        product_id = m.group(1)
        body = m.group("body")
        title_m = _TITLE_RE.search(body)
        price_m = _PRICE_RE.search(body)
        if not title_m or not price_m:
            return None
        currency, value = price_m.group(1), price_m.group(2)
        return {
            "product_id": product_id,
            "product_name": title_m.group(1).strip()[:500],
            "category": category,
            "price": value,
            "currency": currency or self.currency,
            "available": True,
            "url": page_url,
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
