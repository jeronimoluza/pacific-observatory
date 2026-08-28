"""
Spider for Casa Rica (Paraguay) -- https://www.casarica.com.py/.

WooCommerce store (ecommercepro theme; wp-json/wc/store/v1 REST API 404s)
serving full product cards with price directly in server-rendered category
HTML: 261 leaf categories, extracted from the homepage "catalogo" nav and
listed in _casarica_py_categories.txt. Category page 1 is
/catalogo/<slug>; further pages use dot notation /catalogo/<slug>.<N>
(not a query string), linked from an "a.next.page-numbers" element when
present.

Re-verified live 2026-08-06: GET /catalogo/almacen-c1 -> 200, 287KB, 20
real products across 5 paginated pages. Sample: 'COQUITIN BLANCO X KG'
PYG 29.500 (digits-only parse -> 29500; Guaraní has no minor unit).
Currency PYG matches countries.yaml. Product cards carry a
data-product_id and a permalink of shape "<slug>-p<id>", both unique per
SKU (no synthetic-url dedup risk).
"""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.casarica.com.py"
_CATEGORY_LIST_PATH = Path(__file__).parent / "_casarica_py_categories.txt"
MAX_PAGES_PER_CATEGORY = 20


def _load_categories() -> list[str]:
    return [
        line.strip()
        for line in _CATEGORY_LIST_PATH.read_text().splitlines()
        if line.strip()
    ]


class CasaricaPySpider(scrapy.Spider):
    name = "casarica_py"
    allowed_domains = ["casarica.com.py"]
    currency = "PYG"
    language = "es"

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
                f"{_BASE}/catalogo/{slug}",
                callback=self.parse_category,
                meta={"slug": slug, "page": 1},
            )

    def parse_category(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]
        products = response.css("div.product")
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
        if products and page < MAX_PAGES_PER_CATEGORY:
            next_href = response.css("a.next.page-numbers::attr(href)").get()
            if next_href:
                yield scrapy.Request(
                    urljoin(_BASE, next_href),
                    callback=self.parse_category,
                    meta={"slug": slug, "page": page + 1},
                )
