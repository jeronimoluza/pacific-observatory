"""
Spider for Escape Beauty (Ramsey, Isle of Man) - https://escapebeauty.co.im/
Home-based salon; the homepage carries the price lists as
ul.ro-option > li "Treatment name £NN" under h5 group headings. The WooCommerce
Store API is empty, so this reads the HTML. Page family: listing.
Prices are GBP. Each treatment gets a fragment URL so the pipeline's
URL de-duplication keeps every row.
"""

import re
from urllib.parse import quote

import scrapy


class EscapebeautyImSpider(scrapy.Spider):
    name = "escapebeauty_im"
    allowed_domains = ["escapebeauty.co.im"]
    base_url = "https://escapebeauty.co.im/"
    currency = "GBP"
    language = "en"
    custom_settings = {"DOWNLOAD_DELAY": 2.0}

    async def start(self):
        yield scrapy.Request(self.base_url, callback=self.parse_prices)

    def parse_prices(self, response):
        scraped_at = response.headers.get("Date", b"").decode("utf-8")
        for block in response.css("div.ro-membership-item"):
            group = " ".join(block.css("h5 ::text").getall()).strip() or None
            for li in block.css("ul.ro-option > li"):
                text = " ".join(li.css("::text").getall()).strip()
                m = re.match(r"^(.*?)\s*£\s*([0-9]+(?:\.[0-9]{1,2})?)\b", text)
                if not m or not m.group(1):
                    continue
                name = m.group(1).strip(" -:")
                yield {
                    "product_id": None,
                    "product_name": name,
                    "price": m.group(2),
                    "currency": self.currency,
                    "category": group,
                    "url": f"{response.url}#{quote(name)}",
                    "language": self.language,
                    "scraped_at": scraped_at,
                }
