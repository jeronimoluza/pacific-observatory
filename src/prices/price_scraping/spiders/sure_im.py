"""
Spider for Sure Isle of Man handset shop - https://www.sure.com/isleofman/
Telco device deals: product-card blocks on the Tech Deals and Refurbished
Phones pages. Each card has a "Pay Monthly" tab (36-month instalment, not a
price of the item) and a "Buy Now" tab (outright handset price). Only the
Buy Now price is emitted. Page family: listing. Prices are GBP.
robots.txt asks for Crawl-delay 5.
"""

import re
from urllib.parse import quote

import scrapy


class SureImSpider(scrapy.Spider):
    name = "sure_im"
    allowed_domains = ["sure.com", "www.sure.com"]
    pages = [
        "https://www.sure.com/isleofman/mobile/tech-deals/",
        "https://www.sure.com/isleofman/mobile/refurbished-phones/",
    ]
    currency = "GBP"
    language = "en"
    custom_settings = {"DOWNLOAD_DELAY": 5.0, "CONCURRENT_REQUESTS_PER_DOMAIN": 1}

    async def start(self):
        for url in self.pages:
            yield scrapy.Request(url, callback=self.parse_cards)

    @staticmethod
    def _price(node):
        txt = "".join(node.css("::text").getall())
        txt = re.sub(r"\s+", "", txt)
        m = re.search(r"£([0-9][0-9,]*)(?:\.([0-9]{1,2}))?", txt)
        if not m:
            return None
        return m.group(1).replace(",", "") + ("." + m.group(2) if m.group(2) else "")

    def parse_cards(self, response):
        scraped_at = response.headers.get("Date", b"").decode("utf-8")
        section = response.css("h2 ::text").get()
        for card in response.css("div.product-card"):
            title = " ".join(card.css(".product-card__title ::text").getall()).strip()
            tabs = [
                " ".join(t.css("::text").getall()).strip().lower()
                for t in card.css(".product-card__details-tab")
            ]
            blocks = card.css(".product-card__content")
            price = None
            for tab, block in zip(tabs, blocks):
                if "buy" in tab:
                    price = self._price(block.css(".product-card__price"))
            if price is None and not tabs:
                price = self._price(card.css(".product-card__price"))
            if not title or price is None:
                continue
            yield {
                "product_id": None,
                "product_name": title,
                "price": price,
                "currency": self.currency,
                "category": "refurbished phones" if "refurbished" in response.url else (section or "tech deals").strip(),
                "url": f"{response.url}#{quote(title)}",
                "language": self.language,
                "scraped_at": scraped_at,
            }
