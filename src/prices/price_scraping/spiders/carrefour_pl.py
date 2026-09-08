"""
Spider for Carrefour Poland (Online) — https://www.carrefour.pl/.

Next.js storefront, server-rendered: every category page embeds the full
product listing (with prices) in a `__NEXT_DATA__` JSON blob at
`props.initialState.products.data`, no client hydration needed. Pagination
is a plain `?page=N` query param -- verified live that page 1 and page 2 of
`/artykuly-spozywcze` return disjoint product sets (`totalCount` 4,815,
60 products/page -> 81 pages).

Each product entry carries `product.name`, `product.code` (EAN barcode,
used as product_id), `productCategories[0].categoryName` (leaf category),
and `actualSku.amount.actualGrossPrice` (PLN). The site also exposes
`actualSku.lowestAmount.actualGrossPrice` -- the EU Price Indication
Directive Article 6a "lowest price in the last 30 days" field the shard's
AI_NOTES flagged to test for; it IS present here (e.g. one SKU showed
current 5.29 zl vs. a 30-day-low of 4.59 zl), but this spider only emits
the current shelf price -- the pre-reduction field is available for a
future bounded-price-history pass, not consumed here.

Walk strategy: the ~14 top-level category slugs discovered from the
homepage nav are each paginated via ?page=N until a page returns no
products or the declared totalPages is exceeded -- this reaches every
leaf subcategory since Carrefour's `/artykuly-spozywcze` (etc.) listing is
the union of all its children, not just direct products.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.carrefour.pl"
_TOP_CATEGORIES = [
    "artykuly-spozywcze",
    "dania-gotowe-i-przystawki",
    "dla-zwierzat",
    "drogeria-kosmetyki-i-zdrowie",
    "dziecko",
    "mieso",
    "mleko-nabial-jaja",
    "mrozonki",
    "napoje",
    "owoce-warzywa-ziola",
    "piekarnia-ciastkarnia",
    "ryby-i-owoce-morza",
    "wedliny-kielbasy",
    "zdrowa-zywnosc",
]
_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)
MAX_PAGES_PER_CATEGORY = 90  # safety cap, above the ~81-page observed max


class CarrefourPlSpider(scrapy.Spider):
    name = "carrefour_pl"
    allowed_domains = ["carrefour.pl"]
    currency = "PLN"
    language = "pl"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        for slug in _TOP_CATEGORIES:
            yield scrapy.Request(
                f"{_BASE}/{slug}?page=1",
                callback=self.parse_category,
                meta={"slug": slug, "page": 1},
            )

    def parse_category(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]
        m = _NEXT_DATA_RE.search(response.text)
        if not m:
            logger.warning("carrefour_pl: no __NEXT_DATA__ on %s", response.url)
            return
        try:
            data = json.loads(m.group(1))
        except (ValueError, TypeError):
            logger.warning("carrefour_pl: bad JSON on %s", response.url)
            return

        try:
            products_data = data["props"]["initialState"]["products"]["data"]
        except (KeyError, TypeError):
            logger.warning("carrefour_pl: unexpected shape on %s", response.url)
            return

        content = products_data.get("content") or []
        total_pages = products_data.get("totalPages") or 1
        logger.info(
            "carrefour_pl: %s page=%d -> %d products (totalPages=%s)",
            slug,
            page,
            len(content),
            total_pages,
        )

        for entry in content:
            item = self._item(entry, response.url)
            if item:
                yield item

        if content and page < total_pages and page < MAX_PAGES_PER_CATEGORY:
            nxt = page + 1
            yield scrapy.Request(
                f"{_BASE}/{slug}?page={nxt}",
                callback=self.parse_category,
                meta={"slug": slug, "page": nxt},
            )

    def _item(self, entry, page_url):
        product = entry.get("product") or {}
        actual_sku = entry.get("actualSku") or {}
        amount = actual_sku.get("amount") or {}
        name = product.get("name") or entry.get("name")
        price = amount.get("actualGrossPrice")
        if not name or price in (None, "", 0):
            return None

        categories = entry.get("productCategories") or []
        category = categories[0].get("categoryName") if categories else None
        slug = entry.get("slug") or entry.get("defaultCategorySlug")
        url = f"{_BASE}/p/{slug}" if slug else page_url

        return {
            "product_id": product.get("code") or product.get("id") or url,
            "product_name": str(name).strip()[:500],
            "category": category,
            "price": str(price),
            "currency": self.currency,
            "available": actual_sku.get("status") == "ENABLED",
            "url": url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
