"""
Spider for Supermercados Pueblo (Puerto Rico) - https://puebloweb.com/.

Bespoke Alpine.js storefront (not one of the reusable base platforms). The
listing HTML itself carries no server-rendered products — the grid is filled
client-side by fetching `/controllers/products.html?category_id=<id>&
category_level=1&type=category&page=<n>&sort=&query=`, which is a plain,
unauthenticated, cookie-free HTML-fragment endpoint. Verified live 2026-09-01:
9 top-level departments (category_id 1-9, names below), 18 products per page,
pages advance through genuinely distinct SKUs (checked category_id=1 to 24
pages / 432 unique products with zero repeats), and the endpoint returns a
clean empty fragment past the true last page (checked category_id=3 at
page=50/80/100/.../500 - all empty, no re-served last page). No auth, no
Playwright needed.

Each product card carries: PDP href `/productos/<sku>/<slug>`, a combined
brand+description text block, a unit/pack-size line (e.g. "1LB", "32 OZ"),
and a price line in one of two shapes: "$1.29 LB" (per-unit) or "2/$5.00"
(multi-buy - price is amount/count).
"""

import logging
import re

import scrapy

logger = logging.getLogger(__name__)

# multi-buy shape first ("2/$5.00"), plain shape second ("$1.29 LB")
_MULTIBUY_RE = re.compile(r"(\d+)\s*/\s*\$([\d,]+\.\d{2})")
_PLAIN_RE = re.compile(r"\$([\d,]+\.\d{2})")


def _parse_price(text):
    if not text:
        return None
    text = text.strip()
    m = _MULTIBUY_RE.search(text)
    if m:
        count = float(m.group(1))
        amount = float(m.group(2).replace(",", ""))
        return round(amount / count, 2) if count else None
    m = _PLAIN_RE.search(text)
    if m:
        return float(m.group(1).replace(",", ""))
    return None


class PuebloPrSpider(scrapy.Spider):
    name = "pueblo_pr"
    allowed_domains = ["puebloweb.com"]
    currency = "USD"

    CATEGORIES = {
        "1": "Provisiones",
        "2": "Salud y Belleza",
        "3": "Mascotas",
        "4": "Hogar",
        "5": "Frutas y Vegetales",
        "6": "Cervezas, Vinos y Licores",
        "7": "Carnes, Aves y Pescados",
        "8": "Lacteos, Huevos y Congelados",
        "9": "Panaderia, Reposteria y The Village Good to Go",
    }
    PAGE_SIZE = 18
    # Live 2026-09-01 sizing probe (exponential search) found true last
    # non-empty page between 32 and 256 depending on department; cap well
    # above the largest observed bound (Provisiones, ~256-512) as a safety
    # net against a re-served-last-page loop, not as an expected depth.
    MAX_PAGES_PER_CATEGORY = 600

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 0.3,
        "CONCURRENT_REQUESTS": 8,
    }

    async def start(self):
        for category_id in self.CATEGORIES:
            yield self._category_request(category_id, 1)

    def _category_request(self, category_id, page):
        url = (
            "https://puebloweb.com/controllers/products.html"
            f"?category_id={category_id}&category_level=1&type=category"
            f"&page={page}&sort=&query="
        )
        return scrapy.Request(
            url,
            callback=self.parse_category,
            meta={"category_id": category_id, "page": page},
        )

    def parse_category(self, response):
        category_id = response.meta["category_id"]
        page = response.meta["page"]
        category_name = self.CATEGORIES.get(category_id)
        cards = response.css("div.w-full.text-center")
        logger.info(
            f"pueblo_pr: category={category_name} page={page} cards={len(cards)}"
        )

        for card in cards:
            href = card.css("a::attr(href)").get()
            if not href:
                continue
            url = response.urljoin(href)
            sku_match = re.search(r"/productos/(\d+)/", href)
            product_id = sku_match.group(1) if sku_match else None

            name_parts = card.css(
                "div.mt-2.uppercase.tracking-wide.text-sm ::text"
            ).getall()
            product_name = " ".join(p.strip() for p in name_parts if p.strip())

            price_text = card.css("div.text-lg.font-semibold::text").get()
            price = _parse_price(price_text)

            if not product_name or price is None:
                logger.warning(f"Could not extract product data from {url}")
                continue

            yield {
                "product_id": product_id,
                "product_name": product_name,
                "price": price,
                "currency": self.currency,
                "category": category_name,
                "url": url,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }

        # A full page (== PAGE_SIZE) means more may follow; a short/empty
        # page means the department is exhausted.
        if len(cards) == self.PAGE_SIZE and page < self.MAX_PAGES_PER_CATEGORY:
            yield self._category_request(category_id, page + 1)
