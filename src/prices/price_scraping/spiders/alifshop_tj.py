"""
Spider for Alif Shop (Tajikistan) - alifshop.tj.

Next.js SSR storefront. Category listing pages
(/category/<slug>?cityId=1&page=N) render product cards server-side: each
`div.product-card` holds an `a[href^="/product/"]` link, an `h4` with the
price ("6 160 с."), and a `p.line-clamp-2` with the product name. No PDP
fetch needed - listing pages carry name+price+url in one hop. Pagination is
plain `?page=N`; page N past the last one returns zero product cards
(verified: page 3 has 24 cards, page 50 has 0), so the spider stops on an
empty page. Only 10 `/category/<slug>` links plus the top-level `/groceries`
link are server-rendered on the homepage nav - that is the full seed list,
there is no deeper category tree exposed without JS.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Iterator

import scrapy

from ..archived import row_from_meta, rows_from_jsonld

logger = logging.getLogger(__name__)

_BASE = "https://alifshop.tj"

_CATEGORIES = [
    "avtotovary",
    "knigi",
    "melkaya-bytovaya-tehnika",
    "naushniki-i-aksessuary",
    "noutbuki",
    "obrazovanie",
    "sport-i-hobbi",
    "stroitelstvo-i-remont",
    "tehnika-dlya-krasoty",
    "tovary-dlya-krasoty",
]

_TOP_LEVEL = ["groceries"]

_PRICE_RE = re.compile(r"[\d\s\xa0]+")
_MAX_PAGES = 60


class AlifshopTjSpider(scrapy.Spider):
    name = "alifshop_tj"
    allowed_domains = ["alifshop.tj"]
    currency = "TJS"
    language = "ru"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
    }

    async def start(self):
        for slug in _CATEGORIES:
            yield scrapy.Request(
                f"{_BASE}/category/{slug}?cityId=1&page=1",
                callback=self.parse_list,
                cb_kwargs={"slug": slug, "page": 1, "top_level": False},
            )
        for slug in _TOP_LEVEL:
            yield scrapy.Request(
                f"{_BASE}/{slug}?cityId=1&page=1",
                callback=self.parse_list,
                cb_kwargs={"slug": slug, "page": 1, "top_level": True},
            )

    def parse_list(self, response, slug, page, top_level):
        cards = response.css("div.product-card")
        if not cards:
            logger.info("alifshop_tj: %s page %d empty, stopping", slug, page)
            return

        for card in cards:
            href = card.css("a::attr(href)").get()
            name = card.css("p.line-clamp-2::text").get()
            price_raw = card.css("h4::text").get()
            if not (href and name and price_raw):
                continue
            price_match = _PRICE_RE.search(price_raw)
            if not price_match:
                continue
            price = price_match.group(0).replace("\xa0", "").replace(" ", "").strip()
            if not price:
                continue
            url = response.urljoin(href.split("?")[0])
            yield {
                "product_id": url.rsplit("/product/", 1)[-1]
                if "/product/" in url
                else url,
                "product_name": name.strip()[:500],
                "category": slug,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        if page >= _MAX_PAGES:
            logger.warning("alifshop_tj: %s hit page cap %d", slug, _MAX_PAGES)
            return

        next_page = page + 1
        prefix = "category/" if not top_level else ""
        yield scrapy.Request(
            f"{_BASE}/{prefix}{slug}?cityId=1&page={next_page}",
            callback=self.parse_list,
            cb_kwargs={"slug": slug, "page": next_page, "top_level": top_level},
        )

    # ------------------------------------------------------------------
    # Crawl backfiller (prices/backfill.py's parse_html hook). Archived
    # snapshots here are individual /product/<slug> PDPs (not the /category/
    # listing pages the live crawl walks), but confirmed live 2026-08-18: the
    # PDP template embeds a full server-rendered Product JSON-LD block, so
    # the shared jsonld tier covers this spider on its own.
    # ------------------------------------------------------------------
    @classmethod
    def parse_html(cls, html_text: str, url: str) -> Iterator[dict]:
        """Parse one archived Alif Shop PDP page."""
        rows = rows_from_jsonld(html_text, url)
        if not rows:
            row = row_from_meta(html_text, url)
            rows = [row] if row else []
        for row in rows:
            row.setdefault("currency", cls.currency)
            row.setdefault("language", cls.language)
            yield row
