"""
Spider for Rose Pharmacy (rosepharmacy.com) - national PH drugstore chain.

WooCommerce (Porto theme) storefront that server-renders product cards with
name + PHP price directly in category-listing HTML - no JS hydration or auth
needed. The spider discovers product-category URLs from the /pharmacy/ shop
page, crawls each with WooCommerce page/N pagination, and dedupes by the WP
post id embedded in the card class. Category is derived from the crawled
product-category URL slug (per-product rel=tag labels occasionally carry promo
text rather than a taxonomy term).
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.rosepharmacy.com"
_SHOP = _BASE + "/pharmacy/"
_CAT_RE = re.compile(r"/product-category/([^?]+)")
_POST_RE = re.compile(r"post-(\d+)")


class RosePharmacySpider(scrapy.Spider):
    name = "rose_pharmacy"
    allowed_domains = ["rosepharmacy.com"]
    currency = "PHP"
    language = "en"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seen_ids = set()

    async def start(self):
        yield scrapy.Request(_SHOP, callback=self.parse_shop)

    def parse_shop(self, response):
        cat_urls = set(
            response.css('a[href*="/product-category/"]::attr(href)').getall()
        )
        logger.info("rose_pharmacy: found %d category urls", len(cat_urls))
        for url in cat_urls:
            yield scrapy.Request(url, callback=self.parse_category)

    def _category_label(self, url):
        m = _CAT_RE.search(url)
        if not m:
            return None
        seg = m.group(1).rstrip("/").split("/")[-1]
        return seg.replace("-", " ").strip() or None

    def parse_category(self, response):
        category = self._category_label(response.url)
        scraped_at = datetime.now(timezone.utc).isoformat()

        cards = response.css("div.porto-tb-item")
        yielded = 0
        for card in cards:
            name = card.css("h3.post-title a::text").get()
            url = card.css("h3.post-title a::attr(href)").get()
            price = card.css(".tb-woo-price .woocommerce-Price-amount bdi::text").get()
            if not name or not url or not price:
                continue

            m = _POST_RE.search(card.attrib.get("class", ""))
            product_id = m.group(1) if m else None
            if product_id and product_id in self._seen_ids:
                continue
            if product_id:
                self._seen_ids.add(product_id)

            yielded += 1
            yield {
                "product_id": product_id,
                "product_name": name.strip(),
                "price": price.strip(),
                "currency": self.currency,
                "category": category,
                "url": url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        if yielded:
            next_page = (
                response.css("a.next.page-numbers::attr(href)").get()
                or response.css("nav.woocommerce-pagination a.next::attr(href)").get()
            )
            if next_page:
                yield scrapy.Request(next_page, callback=self.parse_category)

    def errback(self, failure):
        logger.error(
            "rose_pharmacy: request failed %s — %r",
            failure.request.url,
            failure.value,
        )
