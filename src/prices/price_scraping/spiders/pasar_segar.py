"""
Spider for Pasar Segar (Indonesia) - https://pasarsegar.co.id/

WooCommerce (Martfury theme) multi-vendor fresh-market marketplace. Product
name, merchant, price and PDP URL are present directly in server-rendered
product-category listing HTML, so this spider scrapes listing pages only (no
PDP visits needed). Category URLs are discovered from the homepage nav
(/product-category/<slug>/), then each category is paginated via the
"next" page-numbers link.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://pasarsegar.co.id"
CATEGORY_RE = re.compile(r"/product-category/([a-z0-9-]+)/")
ID_RE = re.compile(r"[?&]product_id=(\d+)")


class PasarSegarSpider(scrapy.Spider):
    name = "pasar_segar"
    allowed_domains = ["pasarsegar.co.id"]
    start_urls = [f"{_BASE}/"]
    currency = "IDR"
    language = "id"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 3,
        "DOWNLOAD_DELAY": 1,
    }

    def parse(self, response):
        links = set(response.css('a[href*="/product-category/"]::attr(href)').getall())
        cats = set()
        for link in links:
            m = CATEGORY_RE.search(link)
            if m:
                cats.add(m.group(1))
        logger.info("pasar_segar: found %d categories", len(cats))
        for slug in sorted(cats):
            yield scrapy.Request(
                f"{_BASE}/product-category/{slug}/",
                callback=self.parse_category,
                meta={"category": slug},
            )

    def parse_category(self, response):
        category = response.meta["category"]
        scraped_at = datetime.now(timezone.utc).isoformat()

        cards = response.css("li.product.type-product")
        yielded = 0
        for card in cards:
            name = card.css("h2.woo-loop-product__title a::text").get()
            href = card.css("h2.woo-loop-product__title a::attr(href)").get()
            merchant = card.css("a.wcfm_dashboard_item_title::text").get()

            prices = [
                t.strip()
                for t in card.css(
                    ".mf-product-price-box .woocommerce-Price-amount bdi::text"
                ).getall()
                if t.strip()
            ]
            price = prices[-1].replace(".", "").replace(",", "") if prices else None

            if not name or not price:
                continue

            product_id = None
            if href:
                pm = ID_RE.search(href)
                product_id = pm.group(1) if pm else None

            yield {
                "product_id": product_id,
                "product_name": name.strip(),
                "price": price,
                "currency": self.currency,
                "category": category,
                "merchant": merchant.strip() if merchant else None,
                "url": href or response.url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
            yielded += 1

        next_page = response.css("a.next.page-numbers::attr(href)").get()
        if next_page:
            yield scrapy.Request(
                next_page, callback=self.parse_category, meta={"category": category}
            )
        logger.info(
            "pasar_segar: category=%s url=%s yielded=%d",
            category,
            response.url,
            yielded,
        )
