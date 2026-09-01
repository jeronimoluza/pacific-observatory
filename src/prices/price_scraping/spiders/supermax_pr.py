"""
Spider for SuperMax Online (Puerto Rico) - https://www.supermaxonline.com/.

Bespoke jQuery storefront (same "load more" AJAX-grid shape as pueblo_pr,
different vendor). The department listing page (e.g. /guaynabo/lacteos/)
ships an empty `<div class="products-grid" id="products"></div>` - the
actual catalog is filled by POSTing to `/products-grid-data.html` with
`department=<id>&draw=<n>` (plain form POST, no auth/cookie required,
verified live with a cold curl_cffi session). `draw` pages through 36
products at a time; verified live 2026-09-01 on department=1 (Carnes y
Mariscos): draw=0/10 return distinct SKU sets, draw=20+ returns a clean
empty fragment (not a re-served last page) and stays empty through draw=150.

8 of 9 nav departments expose a numeric or slug `data-department` id
(organico is a slug, the rest are numeric); "cenas" has no products-grid
on its own page (likely a deli-mode subview) and is skipped rather than
guessed.

Price text has four shapes, all handled by `_parse_price`:
  "$4.99"                              -> 4.99
  "$4.99<i>...</i> LB"                 -> 4.99 (per-lb; <i> suffix stripped)
  "2/$5.00"                            -> 2.50 (multi-buy: amount/count)
  "97&#162;" / "97¢"              -> 0.97 (cents-only, no store minor-unit API)
"""

import logging
import re

import scrapy

logger = logging.getLogger(__name__)

_MULTIBUY_RE = re.compile(r"(\d+)\s*/\s*\$([\d,]+\.\d{2})")
_DOLLAR_RE = re.compile(r"\$([\d,]+\.\d{2})")
_CENTS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:\xa2|&#162;|¢)")


def _parse_price(text):
    if not text:
        return None
    text = text.strip()
    m = _MULTIBUY_RE.search(text)
    if m:
        count = float(m.group(1))
        amount = float(m.group(2).replace(",", ""))
        return round(amount / count, 2) if count else None
    m = _DOLLAR_RE.search(text)
    if m:
        return float(m.group(1).replace(",", ""))
    m = _CENTS_RE.search(text)
    if m:
        return round(float(m.group(1)) / 100, 2)
    return None


class SupermaxPrSpider(scrapy.Spider):
    name = "supermax_pr"
    allowed_domains = ["supermaxonline.com"]
    currency = "USD"

    # Guaynabo store; verified live 2026-09-01. "cenas" nav item has no
    # products-grid div on its own page and is intentionally omitted.
    DEPARTMENTS = {
        "1": "Carnes y Mariscos",
        "50": "Deli y Bakery",
        "80": "Frutas y Vegetales",
        "153": "Hogar, Salud y Belleza",
        "264": "Lacteos",
        "331": "Licores",
        "421": "Provisiones",
        "organico": "Organico",
    }
    PAGE_SIZE = 36
    MAX_DRAWS_PER_DEPARTMENT = 200

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 0.3,
        "CONCURRENT_REQUESTS": 8,
    }

    async def start(self):
        for department_id in self.DEPARTMENTS:
            yield self._department_request(department_id, 0)

    def _department_request(self, department_id, draw):
        return scrapy.FormRequest(
            "https://www.supermaxonline.com/products-grid-data.html",
            formdata={
                "draw": str(draw),
                "department": department_id,
                "category": "",
                "subcategory": "",
                "supplier": "",
                "skus": "",
                "related": "",
                "previouslyordered": "",
                "onlypromo": "",
                "exclusives": "false",
                "newProducts": "false",
                "shopper": "false",
                "shopperPage": "0",
                "deli": "false",
                "deliCategory": "",
                "terms": "",
                "sortby": "",
            },
            callback=self.parse_department,
            meta={"department_id": department_id, "draw": draw},
        )

    def parse_department(self, response):
        department_id = response.meta["department_id"]
        draw = response.meta["draw"]
        department_name = self.DEPARTMENTS.get(department_id)
        cards = response.css("div.product-grid-item")
        logger.info(
            f"supermax_pr: department={department_name} draw={draw} cards={len(cards)}"
        )

        for card in cards:
            href = card.css("h3 a::attr(href)").get() or card.css("a::attr(href)").get()
            if not href:
                continue
            url = response.urljoin(href)
            product_id = card.css("input[name='sku']::attr(value)").get()
            product_name = (
                card.css("h3 a::attr(title)").get() or card.css("h3 a::text").get()
            )
            if product_name:
                product_name = product_name.strip()

            price_html = card.css("p.precio").get()
            price = _parse_price(price_html)

            if not product_name or price is None:
                logger.warning(f"Could not extract product data from {url}")
                continue

            yield {
                "product_id": product_id,
                "product_name": product_name,
                "price": price,
                "currency": self.currency,
                "category": department_name,
                "url": url,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }

        if len(cards) == self.PAGE_SIZE and draw + 1 < self.MAX_DRAWS_PER_DEPARTMENT:
            yield self._department_request(department_id, draw + 1)
