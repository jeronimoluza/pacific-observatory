"""
Spider for Supermercados Amigo (Puerto Rico) - https://www.amigo.com/.

Same platform and page shape as `pueblo_pr` (Supermercados Amigo and
Supermercados Pueblo share a corporate parent and the same "PO BOX 1967,
Carolina, Puerto Rico" HQ, per the footer on both sites and Wikipedia's
"Amigo Supermarkets... owned by Pueblo"). Confirmed to be a distinct
retail banner rather than a duplicate of pueblo_pr, not just a rebrand:
department category_id values coincide (1-9), and a live 2026-09-01 sample
of 90 SKUs each from category_id=1 found 84% SKU overlap but genuinely
different shelf prices on 17 of 76 (22%) common SKUs (e.g. sku 127472:
Amigo $0.79 vs Pueblo $0.99) - two independently-priced storefronts on a
shared catalog backend, not the same shelf counted twice.

Endpoint, pagination, and price-text shapes are identical to pueblo_pr -
see that file's docstring for the verification detail. Department names
differ slightly on this domain (`panaderia-y-reposteria` here vs pueblo's
longer combined name); ids are otherwise the same.
"""

import logging
import re

import scrapy

logger = logging.getLogger(__name__)

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


class AmigoPrSpider(scrapy.Spider):
    name = "amigo_pr"
    allowed_domains = ["amigo.com"]
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
        "9": "Panaderia y Reposteria",
    }
    PAGE_SIZE = 18
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
            "https://www.amigo.com/controllers/products.html"
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
            f"amigo_pr: category={category_name} page={page} cards={len(cards)}"
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

        if len(cards) == self.PAGE_SIZE and page < self.MAX_PAGES_PER_CATEGORY:
            yield self._category_request(category_id, page + 1)
