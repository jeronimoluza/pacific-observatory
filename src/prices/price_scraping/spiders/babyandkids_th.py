"""Baby & Kids Thailand LnwShop category page."""

from datetime import datetime, timezone

import scrapy


class BabyAndKidsThSpider(scrapy.Spider):
    name = "babyandkids_th"
    allowed_domains = ["www.babyandkidsthailand.com", "babyandkidsthailand.com"]
    start_urls = ["https://www.babyandkidsthailand.com/category"]
    currency = "THB"
    language = "th"
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def parse(self, response):
        for card in response.css("div.productArea.productItem"):
            name = " ".join(card.css("div.product_name a::text").getall()).strip()
            if not name:
                name = " ".join(card.css("img::attr(alt)").getall()).strip()
            price_node = card.css("div.product_price::attr(realprice)").get()
            if not name or not price_node:
                continue
            try:
                price = float(str(price_node).replace(",", ""))
            except ValueError:
                continue
            href = card.css("div.product_name a::attr(href)").get()
            status = " ".join(card.css("div.product_button *::text").getall()).strip()
            yield {
                "product_id": card.attrib.get("proid") or "",
                "product_name": name[:500],
                "category": "baby, toys, nursery furniture",
                "price": f"{price:.2f}",
                "currency": self.currency,
                "available": "สินค้าหมด" not in status,
                "url": response.urljoin(href) if href else response.url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
