"""
Spider for Arete Supermercados (Paraguay) -- https://arete.com.py/.

Same ecommercepro (WooCommerce-derived) storefront family as casarica_py:
server-rendered category pages carry 20 full product cards each, with
`h2.ecommercepro-loop-product__title`, `span.price span.amount` and a
`data-product_id`. `/wp-json/wc/store/v1/products` 404s, so this is an
HTML/parsel spider rather than the Woo Store-API base.

Probed live 2026-09-11: GET /catalogo/almacen-c273 -> HTTP 200, 185KB, 20
products. Sample: 'ACEITUNA NUCETE DESC/PREMIUM 180*24' PYG 28.500
(digits-only parse -> 28500; Guarani has no minor unit). Page 2 at
/catalogo/almacen-c273.2 returns a disjoint set of 20 product ids, so the
dot-notation pagination really paginates (not a re-served first page).

162 leaf categories harvested from the homepage "catalogo" nav, listed in
_arete_py_categories.txt; they span groceries, fresh produce, meat/fish,
dairy, alcohol, pharmacy, household, pet, hardware and bazaar.

Page family parsed: listing (category pages). Product permalinks embed a
numeric id (<slug>-p<id>) so there is no synthetic-url dedup risk.
"""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://arete.com.py"
_CATEGORY_LIST_PATH = Path(__file__).parent / "_arete_py_categories.txt"
MAX_PAGES_PER_CATEGORY = 30


def _load_categories() -> list[str]:
    return [
        line.strip()
        for line in _CATEGORY_LIST_PATH.read_text().splitlines()
        if line.strip()
    ]


class AretePySpider(scrapy.Spider):
    name = "arete_py"
    allowed_domains = ["arete.com.py"]
    currency = "PYG"
    language = "es"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "DOWNLOAD_TIMEOUT": 60,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        for slug in _load_categories():
            yield scrapy.Request(
                f"{_BASE}/catalogo/{slug}",
                callback=self.parse_category,
                meta={"slug": slug, "page": 1},
            )

    def parse_category(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]
        products = response.css("div.product")
        n = 0
        for p in products:
            href = p.css("a.ecommercepro-LoopProduct-link::attr(href)").get()
            if not href:
                continue
            name = p.css("h2.ecommercepro-loop-product__title::text").get()
            if not name:
                name = p.css("img::attr(alt)").get()
            name = (name or "").strip()
            amounts = [
                a.strip()
                for a in p.css("span.price span.amount::text").getall()
                if a.strip()
            ]
            amount = amounts[-1] if amounts else None
            if not name or not amount:
                continue
            price = re.sub(r"[^\d]", "", amount)
            if not price:
                continue
            pid_match = re.search(r"-p(\d+)$", href)
            product_id = pid_match.group(1) if pid_match else href
            n += 1
            yield {
                "product_id": product_id,
                "product_name": name,
                "category": slug,
                "price": price,
                "currency": self.currency,
                "url": urljoin(_BASE, href),
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        logger.info(f"arete_py: {slug} page={page} items={n}")
        if products and page < MAX_PAGES_PER_CATEGORY:
            next_href = response.css("a.next.page-numbers::attr(href)").get()
            if next_href:
                yield scrapy.Request(
                    urljoin(_BASE, next_href),
                    callback=self.parse_category,
                    meta={"slug": slug, "page": page + 1},
                )
        elif products and page >= MAX_PAGES_PER_CATEGORY:
            logger.warning(
                f"arete_py: {slug} hit MAX_PAGES_PER_CATEGORY={MAX_PAGES_PER_CATEGORY}"
                " -- the tail of this category was NOT collected"
            )
