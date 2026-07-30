"""
Spider for Eigigu Supermarket (Nauru) — eigigu.net

Ecwid "Instant Site" storefront. The pre-verified plan called for hitting the
Ecwid Storefront REST API (app.ecwid.com/api/v3/<store_id>/products), but that
endpoint 403s without an OAuth/public access token and no such token is exposed
client-side (Instant Sites render server-side, unlike the JS-widget Ecwid
embeds that carry a public token). Category and product-listing pages are
server-rendered HTML with real AUD prices, so this is a Tier 1A scrapy_html
spider instead: crawl the 9 top-level category pages and parse each
`.grid-product__wrap` card for id/name/price. Client-side pagination
(`.pager__button--next`) is JS-driven and not SSR — `?page=N` on the category
URL returns page 1 again — so only the first page per category is crawled.
Rows with a $0.00 placeholder price (out-of-stock / unpriced items) are
dropped.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

CATEGORY_URLS = [
    "https://eigigu.net/BABY-CARE-c196932251",
    "https://eigigu.net/CEREAL-c196859255",
    "https://eigigu.net/CHILLED-JUICES-&-DRINKS-c196859253",
    "https://eigigu.net/LAUNDRY-&-HOUSEHOLD-c196538753",
    "https://eigigu.net/PANTRY-c194127001",
    "https://eigigu.net/PERSONAL-CARE-c196934751",
    "https://eigigu.net/POULTRY-MEAT-&-SEAFOOD-c193591299",
    "https://eigigu.net/SNACKS-&-CONFECTIONERY-c196905277",
    "https://eigigu.net/TIN-FOODS-c198341001",
]

_PRICE_RE = re.compile(r"AU\$?\s*([\d,]+\.\d{2})")


class EigiguSupermarketSpider(scrapy.Spider):
    name = "eigigu_supermarket"
    allowed_domains = ["eigigu.net"]
    currency = "AUD"

    custom_settings = {
        "DOWNLOAD_DELAY": 1,
        "CONCURRENT_REQUESTS": 1,
    }

    async def start(self):
        for url in CATEGORY_URLS:
            yield scrapy.Request(url, callback=self.parse_category)

    def parse_category(self, response):
        category = (response.css(".page-title__name::text").get() or "").strip()
        if not category:
            slug = response.url.rsplit("/", 1)[-1].rsplit("-c", 1)[0]
            category = slug.replace("-", " ").title()

        wraps = response.css("div.grid-product__wrap")
        logger.info(
            f"eigigu_supermarket: category={category!r} found {len(wraps)} cards"
        )
        for wrap in wraps:
            product_id = wrap.attrib.get("data-product-id")
            name = wrap.css(".grid-product__title-inner::text").get()
            price_text = " ".join(
                t.strip()
                for t in wrap.css(".grid-product__price-value::text").getall()
                if t.strip()
            )
            url = wrap.css("a.grid-product__title::attr(href)").get()
            if not (product_id and name and price_text and url):
                continue

            m = _PRICE_RE.search(price_text)
            if not m:
                continue
            price = m.group(1).replace(",", "")
            if float(price) <= 0:
                continue

            yield {
                "product_id": product_id,
                "product_name": name.strip()[:500],
                "price": price,
                "currency": self.currency,
                "category": category,
                "url": response.urljoin(url),
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            logger.info(
                f"eigigu_supermarket: scraped {name!r} @ {self.currency} {price}"
            )
