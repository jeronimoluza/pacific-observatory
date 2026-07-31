"""
Spider for Health Lane Family Pharmacy (Malaysia) - https://estore.healthlane.com.my/

OpenCart-based O2O pharmacy catalogue. Product name + price are present
directly in server-rendered category listing HTML, so this spider scrapes
listing pages only (no PDP visits needed). Category slugs are the site's
top-level nav taxonomy; pagination follows the "of N (M Pages)" listing
footer.
"""

import logging
import re

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://estore.healthlane.com.my"

CATEGORY_SLUGS = [
    "supplement",
    "mother-baby-care",
    "young-beauty",
    "personal_care",
    "OTC-First-Aid",
    "House-Hold",
    "food-and-beverage",
    "nutrition",
]

PAGES_RE = re.compile(r"\((\d+)\s*Pages\)")


class HealthLaneSpider(scrapy.Spider):
    name = "health_lane"
    allowed_domains = ["estore.healthlane.com.my"]
    currency = "MYR"

    def start_requests(self):
        for slug in CATEGORY_SLUGS:
            url = f"{BASE_URL}/{slug}"
            yield scrapy.Request(
                url, callback=self.parse_category, meta={"base_url": url, "page": 1}
            )

    def parse_category(self, response):
        base_url = response.meta["base_url"]
        page = response.meta["page"]

        cards = response.css("div.product-grid .product.clearfix")
        for card in cards:
            name = card.css(".card-body .name a::text").get()
            url = card.css(".card-body .name a::attr(href)").get()
            price_text = " ".join(
                card.css(".card-body .price ::text, .card-body .price::text").getall()
            )
            prices = re.findall(r"RM\s?[\d,]+\.\d{2}", price_text)
            if not name or not prices:
                continue
            price = prices[-1]

            yield {
                "product_id": None,
                "product_name": name.strip(),
                "price": price.strip(),
                "currency": self.currency,
                "category": base_url.rsplit("/", 1)[-1]
                .replace("-", " ")
                .replace("_", " "),
                "url": url,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }

        m = PAGES_RE.search(response.text)
        total_pages = int(m.group(1)) if m else 1
        if page < total_pages:
            next_page = page + 1
            yield scrapy.Request(
                f"{base_url}?page={next_page}",
                callback=self.parse_category,
                meta={"base_url": base_url, "page": next_page},
            )
