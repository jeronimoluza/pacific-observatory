"""
Spider for Cijene.hr — https://www.cijene.hr/.

A long-running (since 2001) Croatian multi-retailer price-comparison
aggregator. Server-rendered, custom PHP storefront (no Next.js/Nuxt marker).
Category listing pages (e.g. /alge, /mlijeko, /med) render product cards
directly in HTML with the *minimum* price across all carried retailers
("od 2,29 €" = "from EUR 2.29") plus a location count ("247 lokacija" =
247 retail locations carrying the item) -- this spider records the "od"
price as `price` since that is the only price the listing page exposes.

Verified live 2026-09-06: GET /alge -> 200, 35 products incl. "Saitaku
sušene morske alge Nori 14 g" od 2,29 € (247 lokacija). The page-size
selector (`kPostavke.pregledBrojProizvoda`, options 20/40/60/80/100/160/300)
is honoured as a query param, so `?kPostavke.pregledBrojProizvoda=300`
collects up to 300 products per leaf category in one request; `&page=N`
paginates beyond that for larger categories.

Category list (`_cijene_hr_categories.txt`, 136 leaf slugs) was seeded by
crawling the homepage nav plus one level of its sub-nav (e.g. /hrana ->
/alge, /mlijeko, ...) and keeping every distinct single-segment path.
"""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.cijene.hr"
_CATEGORY_LIST_PATH = Path(__file__).parent / "_cijene_hr_categories.txt"
_PAGE_SIZE = 300
_MAX_PAGES = 5

_PRODUCT_BLOCK_RE = re.compile(r'<div class="product">.*?</div>\s*</div>\s*</div>', re.S)
_LINK_RE = re.compile(
    r'<a class="product__link product-title" href="([^"]+cijena-(\d+))"[^>]*>\s*([^<]+?)\s*<'
)
_PRICE_RE = re.compile(r'product__price">\s*(?:od\s*)?([\d.,]+)\s*€')
_LOKACIJA_RE = re.compile(r'>\s*(\d+)\s*[\s\S]{0,120}?lokacij')


def _load_categories():
    return [
        line.strip()
        for line in _CATEGORY_LIST_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class CijeneHrSpider(scrapy.Spider):
    name = "cijene_hr"
    allowed_domains = ["cijene.hr"]
    currency = "EUR"
    language = "hr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        for slug in _load_categories():
            yield scrapy.Request(
                f"{_BASE}/{slug}?kPostavke.pregledBrojProizvoda={_PAGE_SIZE}",
                callback=self.parse_page,
                meta={"slug": slug, "page": 1},
            )

    def parse_page(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]
        blocks = _PRODUCT_BLOCK_RE.findall(response.text)
        scraped_at = datetime.now(timezone.utc).isoformat()
        count = 0
        for block in blocks:
            link_m = _LINK_RE.search(block)
            if not link_m:
                continue
            url_path, pid, name = link_m.groups()
            price_m = _PRICE_RE.search(block)
            if not price_m:
                continue
            price = price_m.group(1).replace(".", "").replace(",", ".")
            count += 1
            yield {
                "product_id": pid,
                "product_name": name.strip()[:500],
                "category": slug,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": f"{_BASE}{url_path}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"cijene_hr: {slug} page={page} items={count}")

        if count >= _PAGE_SIZE and page < _MAX_PAGES:
            yield scrapy.Request(
                f"{_BASE}/{slug}?kPostavke.pregledBrojProizvoda={_PAGE_SIZE}&page={page + 1}",
                callback=self.parse_page,
                meta={"slug": slug, "page": page + 1},
            )
