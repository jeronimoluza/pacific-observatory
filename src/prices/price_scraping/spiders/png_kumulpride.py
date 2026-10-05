"""Kumul Pride Papua New Guinea product listing spider."""
import re
from datetime import datetime, timezone

import scrapy

START_URL = "https://kumulpride.com/"
PRODUCT_SELECTOR = "li.product a[href*='/product/'], div.product a[href*='/product/']"
PRICE_RE = re.compile(r"(\d[\d,]*(?:\.\d{1,2})?)")


class PngKumulprideSpider(scrapy.Spider):
    name = "png_kumulpride"
    allowed_domains = ["kumulpride.com"]
    currency = "USD"
    language = "en"

    async def start(self):
        yield scrapy.Request(START_URL, callback=self.parse)

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        seen = set()
        for anchor in response.css(PRODUCT_SELECTOR):
            href = anchor.attrib.get("href", "")
            product_id = href.rstrip("/").rsplit("/", 1)[-1]
            card = anchor.xpath("ancestor::*[self::li or self::div][contains(@class, 'product')][1]")
            card_text = " ".join(card.css("::text").getall()) if card else ""
            name = (anchor.css(".woocommerce-loop-product__title::text").get() or "").strip()
            price_node = anchor.css(".price ins .amount, .price > .amount, .price .amount")
            price_text = " ".join(price_node.css("::text").getall()) if price_node else card_text
            match = PRICE_RE.search(price_text.replace("\xa0", " "))
            price = match.group(1).replace(",", "") if match else None
            if not product_id or not name or not price or float(price) <= 0 or product_id in seen:
                continue
            seen.add(product_id)
            yield {"product_id": product_id, "product_name": name[:500], "category": "bilums",
                   "price": price, "currency": self.currency, "available": True,
                   "url": response.urljoin(href), "language": self.language,
                   "scraped_at_utc": scraped_at}
