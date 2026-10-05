"""HSD Online Suriname WooCommerce product listing spider."""
import re
from datetime import datetime, timezone

import scrapy

START_URL = "https://www.hsdsonline.com/"
PRODUCT_SELECTOR = ".wd-product.product-grid-item"
PRICE_RE = re.compile(r"SRD\s*([0-9][0-9,.]*)", re.I)


class SurinameHsdsonlineSpider(scrapy.Spider):
    name = "suriname_hsdsonline"
    allowed_domains = ["hsdsonline.com", "www.hsdsonline.com"]
    currency = "SRD"
    language = "en"

    async def start(self):
        yield scrapy.Request(START_URL, callback=self.parse)

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        seen = set()
        for card in response.css(PRODUCT_SELECTOR):
            anchor = card.css("a.wd-product-img-link[href*='/product/']")
            href = anchor.attrib.get("href", "") if anchor else ""
            product_id = href.rstrip("/").rsplit("/", 1)[-1]
            name = (card.css(".wd-entities-title a::text").get() or "").strip()
            price = None
            current = card.css(".price .red-price .woocommerce-Price-amount")
            text = " ".join(current.css("::text").getall()).replace("\xa0", " ")
            match = PRICE_RE.search(text)
            if match:
                price = match.group(1).replace(",", "")
            if not product_id or not name or not price or float(price) <= 0 or product_id in seen:
                continue
            seen.add(product_id)
            yield {"product_id": product_id, "product_name": name[:500], "category": None,
                   "price": price, "currency": self.currency, "available": True,
                   "url": response.urljoin(href), "language": self.language,
                   "scraped_at_utc": scraped_at}
