"""
Spider for MagnumOpt (Kazakhstan) — https://magnumopt.kz/. Wholesale
cash-and-carry arm of the Magnum retail chain.

1C-Bitrix storefront, server-rendered. CSV flagged "some pricing may need
registration" -- untrue for the base unit price: each product card renders
`<div class="item-title"><a href="/catalog/product/<id>-<slug>/"><span>NAME
</span></a></div>` followed by a `price_value`/`price_currency` pair with
no login wall (`"только для..."` gating only applies to a separate B2B
phone line, not the listed prices). Wholesale price-break tiers ("Варианты
цен") appear as additional price_value entries after the same title; the
spider takes the first (base) price.

Re-verified live 2026-08-06: GET /catalog/1365-goroshek-konservirovannyy/
-> 200, 607KB, 12 real products incl. 'Горошек скатерть-самобранка Зел из
Мозг Сортов 420гр ж/б (Ресей/Россия)' KZT 825/шт. No numeric pagination
param found within probe budget (Bitrix "load more" is likely ajax) --
each category page renders a bounded first page only; the 673-slug category
list on the homepage (`_magnumopt_kz_categories.txt`) spans both umbrella
and child nodes, so the union of first-pages still reaches deep leaves
directly.
"""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://magnumopt.kz"
_CATEGORY_LIST_PATH = Path(__file__).parent / "_magnumopt_kz_categories.txt"
_TITLE_RE = re.compile(
    r'class="item-title">\s*<a href="(/catalog/product/[^"]+)"[^>]*><span>([^<]+)</span>'
)
_PRICE_RE = re.compile(
    r'class="price[^"]*"[^>]*data-currency="([A-Z]{3})" data-value="([0-9.]+)"'
)


def _load_categories():
    return [
        line.strip()
        for line in _CATEGORY_LIST_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class MagnumoptKzSpider(scrapy.Spider):
    name = "magnumopt_kz"
    allowed_domains = ["magnumopt.kz"]
    currency = "KZT"
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
        for slug in _load_categories():
            yield scrapy.Request(
                f"{_BASE}/catalog/{slug}/",
                callback=self.parse_page,
                meta={"slug": slug},
            )

    def parse_page(self, response):
        slug = response.meta["slug"]
        text = response.text
        titles = list(_TITLE_RE.finditer(text))
        if not titles:
            return
        scraped_at = datetime.now(timezone.utc).isoformat()
        count = 0
        for i, m in enumerate(titles):
            href, name = m.groups()
            end = titles[i + 1].start() if i + 1 < len(titles) else len(text)
            price_m = _PRICE_RE.search(text, m.end(), end)
            if not price_m:
                continue
            currency, price = price_m.groups()
            product_id = href.rstrip("/").split("/")[-1].split("-", 1)[0]
            count += 1
            yield {
                "product_id": product_id,
                "product_name": name.strip()[:500],
                "category": slug,
                "price": price,
                "currency": currency or self.currency,
                "available": True,
                "url": f"{_BASE}{href}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"magnumopt_kz: {slug} items={count}")
