"""
Spider for Dia (Spain) — https://www.dia.es/.

Discounter supermarket chain. The public sitemap.xml lists 289 category URLs
of shape /<dept>/<subdept>/c/L<id> (flat two-level taxonomy, no parent/child
redundancy), covering the whole catalog; paths are listed in
`_dia_es_categories.txt`.

Category pages are server-rendered with real product cards
(`div.search-product-card`, `object_id` attribute = product id,
`p.search-product-card__product-name` = name,
`p.search-product-card__active-price` = price, e.g. '4,99 €'). Pagination
inserts `/pag-N/` before the `/c/L<id>` suffix (page 1 has no `/pag-N/`
segment). robots.txt explicitly allows only `/pag-1/` through `/pag-5/`
(it disallows `*/pag-*` otherwise), so we cap the walk at page 5 per
category to stay within what the site invites crawlers to fetch.

Re-verified live 2026-08-06: /carnes/cerdo/c/L2014 -> 200, 10 real product
cards incl. 'Cerdo a tacos Selección de Dia 650 g aprox.' 3,89 €;
/carnes/cerdo/pag-2/c/L2014 -> 200, 5 more distinct cards, confirming real
pagination.
"""

import html
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.dia.es"
_CATEGORY_LIST_PATH = Path(__file__).parent / "_dia_es_categories.txt"
_MAX_PAGE = 5  # robots.txt only allows /pag-1/ .. /pag-5/
_PRICE_RE = re.compile(r"([0-9]+,[0-9]+)")


def _load_categories() -> list[str]:
    return [
        line.strip()
        for line in _CATEGORY_LIST_PATH.read_text().splitlines()
        if line.strip()
    ]


def _page_url(path: str, page: int) -> str:
    if page <= 1:
        return f"{_BASE}{path}"
    return f"{_BASE}{path.replace('/c/L', f'/pag-{page}/c/L')}"


class DiaEsSpider(scrapy.Spider):
    name = "dia_es"
    allowed_domains = ["dia.es"]
    currency = "EUR"
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
        for path in _load_categories():
            yield scrapy.Request(
                _page_url(path, 1),
                callback=self.parse_page,
                meta={"path": path, "page": 1},
            )

    def parse_page(self, response):
        path = response.meta["path"]
        page = response.meta["page"]
        category = path.strip("/").split("/c/L")[0].replace("/", " > ")

        cards = response.css("div.search-product-card")
        logger.info(f"dia_es: {path} page={page} count={len(cards)}")
        if not cards:
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        for card in cards:
            product_id = card.attrib.get("object_id")
            name = card.css("p.search-product-card__product-name::text").get()
            price_text = card.css("p.search-product-card__active-price::text").get()
            url = card.css(
                'a[data-test-id="search-product-card-name"]::attr(href)'
            ).get()
            if not product_id or not name or not price_text:
                continue
            m = _PRICE_RE.search(price_text)
            if not m:
                continue
            yield {
                "product_id": product_id,
                "product_name": html.unescape(name).strip()[:500],
                "category": category,
                "price": m.group(1).replace(",", "."),
                "currency": self.currency,
                "available": True,
                "url": f"{_BASE}{url}" if url and url.startswith("/") else (url or ""),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        if page < _MAX_PAGE:
            nxt = page + 1
            yield scrapy.Request(
                _page_url(path, nxt),
                callback=self.parse_page,
                meta={"path": path, "page": nxt},
            )
