"""
Spider for Linella (Moldova) — https://linella.md/.

Server-rendered category pages at /ro/catalog/<slug>?page=N (266 category
slugs, companion `_linella_md_categories.txt`, pulled from the site's own
/ro/catalog nav 2026-08-06). Each product card carries name + price
directly: `<a class="products-catalog-content__name">NAME</a> ...
<span class="price-products-catalog-content__new">19.99</span>`. The
charged price uses one of three classes depending on discount state:
`__new` (discounted), `__static` (regular, no discount), `__old`
(struck-through original, only alongside `__new`) — tried in that order.

Pagination is a real windowed widget (`?page=N`, `pag__next` link) but we
don't trust it to self-terminate cleanly, so — same approach as Parma
(AM) and Glomark (LK) in this batch — we stop once a page yields no
product names beyond what we've already seen for that category.

Re-verified live 2026-08-06: /ro/catalog/apa_minerala -> 200, 514KB, real
product 'CHEILE BICAZULUI Apa minerala plata 2l' 19.99 MDL (discounted
from 23.79); page=2 returns 40 different products, zero overlap with
page=1.
"""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://linella.md"
_CATEGORY_LIST_PATH = Path(__file__).parent / "_linella_md_categories.txt"
_NAME_RE = re.compile(
    r'href="(/ro/catalog/[a-zA-Z0-9_/-]+)\?from=CATALOGUE" class="products-catalog-content__name">'
    r"([^<]*)</a>"
)
_NEW_PRICE_RE = re.compile(r'price-products-catalog-content__new">\s*([0-9.,]+)')
_STATIC_PRICE_RE = re.compile(r'price-products-catalog-content__static">\s*([0-9.,]+)')
_OLD_PRICE_RE = re.compile(r'price-products-catalog-content__old">\s*([0-9.,]+)')
_WINDOW = 1500
MAX_PAGES = 40


def _load_slugs() -> list[str]:
    return [
        line.strip()
        for line in _CATEGORY_LIST_PATH.read_text().splitlines()
        if line.strip()
    ]


class LinellaMdSpider(scrapy.Spider):
    name = "linella_md"
    allowed_domains = ["linella.md"]
    currency = "MDL"
    language = "ro"

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
        for slug in _load_slugs():
            yield scrapy.Request(
                f"{_BASE}/ro/catalog/{slug}?page=1",
                callback=self.parse_category,
                meta={"slug": slug, "page": 1, "seen": set()},
            )

    def parse_category(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]
        seen: set = response.meta["seen"]

        html = response.text
        matches = list(_NAME_RE.finditer(html))
        cards = []
        for i, m in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(html)
            window = html[m.end() : min(end, m.end() + _WINDOW)]
            price_m = (
                _NEW_PRICE_RE.search(window)
                or _STATIC_PRICE_RE.search(window)
                or _OLD_PRICE_RE.search(window)
            )
            price = price_m.group(1) if price_m else None
            cards.append((m.group(1), m.group(2), price))

        new_urls = {c[0] for c in cards if c[2]} - seen
        logger.info(
            f"linella_md: {slug} page={page} cards={len(cards)} new={len(new_urls)}"
        )

        scraped_at = datetime.now(timezone.utc).isoformat()
        for url_path, name, price in cards:
            if url_path not in new_urls:
                continue
            if not name or not price:
                continue
            yield {
                "product_id": url_path.rsplit("/", 1)[-1],
                "product_name": name.strip()[:500],
                "category": slug,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": f"{_BASE}{url_path}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        if new_urls and page < MAX_PAGES:
            seen = seen | new_urls
            yield scrapy.Request(
                f"{_BASE}/ro/catalog/{slug}?page={page + 1}",
                callback=self.parse_category,
                meta={"slug": slug, "page": page + 1, "seen": seen},
            )
