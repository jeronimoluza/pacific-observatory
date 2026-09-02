"""
Spider for CIM Market (Mali) - https://minicim.ml/

Odoo 19 ("website_sale") eCommerce storefront -- 7 physical stores in
Bamako, online ordering with pickup or delivery, currency configured as
XOF with 0 decimal digits (confirmed in the page's odoo.__session_info__
JSON: {"currencies": {"41": {"name": "XOF", ..., "digits": [69, 0]}}}).

Server-rendered category listing pages (Tier 1A) already carry
product_name + price + url per card -- no PDP visit needed. Ten top-level
categories cover the whole catalog (boissons, epicerie-salee,
epicerie-sucree, lait-petit-dej, frais-surgeles, hygiene-beaute,
entretien-maison, bazar-jetable, bebe, divers): a genuine supermarket, not
a specialty store. Verified live 2026-09-01: /shop shows 106 pages x ~100
products/page (~10,600 SKUs); page 1 and page 2 of the un-scoped /shop
listing returned entirely disjoint product sets, confirming real
pagination rather than a re-served single page.

Pagination follows Odoo's own pager: the "next" control
(`span.oi-chevron-right`'s enclosing `<li>`) carries class `disabled` on
the last page, which is the correct, explicit termination signal here --
unlike a Magento storefront that silently re-serves its last page forever
(see references/known_blockers.md), Odoo tells you when to stop.

Prices are French-formatted integers with a (non-breaking) space
thousands separator and NO decimal part -- "3 000" is 3000 XOF, not 3.00.
XOF has no minor unit (see the wave-9 Mali brief); this spider does not
divide by 100.
"""

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://minicim.ml"

CATEGORY_PATHS = [
    "/shop/category/boissons-1",
    "/shop/category/epicerie-sucree-2",
    "/shop/category/epicerie-salee-3",
    "/shop/category/lait-petit-dej-4",
    "/shop/category/frais-surgeles-5",
    "/shop/category/hygiene-beaute-6",
    "/shop/category/entretien-maison-7",
    "/shop/category/bebe-8",
    "/shop/category/bazar-jetable-9",
    "/shop/category/divers-10",
]

_PRODUCT_ID_RE = re.compile(r"-(\d+)$")
_PRICE_CLEAN_RE = re.compile(r"[^\d,.-]")


class MinicimMlSpider(scrapy.Spider):
    name = "minicim_ml"
    allowed_domains = ["minicim.ml"]
    currency = "XOF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        for path in CATEGORY_PATHS:
            yield scrapy.Request(urljoin(BASE_URL, path), callback=self.parse_listing)

    def parse_listing(self, response):
        h1 = response.css("h1 span::text").get()
        category = h1.strip() if h1 else None

        cards = response.css("form.oe_product_cart")
        for card in cards:
            item = self._item(card, category, response.url)
            if item:
                yield item
        logger.info(f"{self.name}: {len(cards)} products on {response.url}")

        # Odoo's pager explicitly disables the "next" control on the last
        # page -- that is the termination signal, not an empty-page guess.
        next_li = response.css("li:has(span.oi-chevron-right)")
        if next_li and "disabled" not in (next_li.attrib.get("class") or ""):
            next_href = next_li.css("a::attr(href)").get()
            if next_href:
                yield scrapy.Request(
                    urljoin(response.url, next_href),
                    callback=self.parse_listing,
                )

    def _item(self, card, category, page_url):
        name = card.css("h2.o_wsale_products_item_title span::text").get()
        href = card.css("a.oe_product_image_link::attr(href)").get()
        price_text = card.css("div.product_price span.oe_currency_value::text").get()

        if not name or not href or price_text is None:
            return None

        name = name.strip()
        url = urljoin(page_url, href)
        price = self._parse_price(price_text)
        if price is None or price <= 0:
            return None

        m = _PRODUCT_ID_RE.search(href)
        product_id = m.group(1) if m else url

        return {
            "product_id": product_id,
            "product_name": name,
            "category": category,
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _parse_price(text: str) -> float | None:
        # French thousands separator (regular or U+00A0 non-breaking space),
        # no decimal part on this site -- "3 000" / "3\xa0000" -> 3000.
        cleaned = text.replace("\xa0", "").replace(" ", "").replace(",", ".")
        cleaned = _PRICE_CLEAN_RE.sub("", cleaned)
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
