"""
Spider for Apex Pharmacy (Malaysia) - https://www.apexpharmacy.com.my/

Custom ASP.NET catalogue. Product name + price are present directly in the
server-rendered Shop-Listing category HTML, so this spider scrapes the
top-level category listing pages only (no PDP visits needed). The site's
"load more" AJAX endpoint (getNextProduct.ashx) returns empty for these
categories in practice, so pagination is not attempted; the fixed
top-level category slugs (from the site's main nav) already yield enough
distinct products per category.
"""

import logging
import re

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.apexpharmacy.com.my"

CATEGORY_SLUGS = [
    "beauty-shape",
    "complete-nutrition",
    "diabetic",
    "for-medical-students",
    "general-health-supplements",
    "heart-health",
    "joint-bone-muscle",
    "massager",
    "otc",
    "personal-care",
    "rehab-aid",
    "sports-nutrition",
]


class ApexPharmacySpider(scrapy.Spider):
    name = "apex_pharmacy"
    allowed_domains = ["www.apexpharmacy.com.my"]
    currency = "MYR"

    def start_requests(self):
        for slug in CATEGORY_SLUGS:
            url = f"{BASE_URL}/Shop-Listing/{slug}/"
            yield scrapy.Request(
                url, callback=self.parse_category, meta={"category": slug}
            )

    def parse_category(self, response):
        category = response.meta["category"]

        for card in response.css("div.product-item"):
            name = card.css("span.product-name a::text").get()
            url = card.css("span.product-name a::attr(href)").get()
            price_text = card.css("span.price::text").get()
            product_id = card.css("img[pid]::attr(pid)").get()

            if not name or not price_text:
                continue

            m = re.search(r"RM\s?[\d,]+\.\d{2}", price_text)
            if not m:
                continue
            price = m.group(0)

            yield {
                "product_id": product_id,
                "product_name": name.strip(),
                "price": price.strip(),
                "currency": self.currency,
                "category": category.replace("-", " "),
                "url": response.urljoin(url) if url else None,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
