"""
Spider for The Lily Retreat Skin & Beauty Rooms (Peel, Isle of Man) -
https://www.thelilyretreatbeautyroom.co.uk/
Weebly store. Seeds from sitemap.xml (/store/pN product pages), parses each
PDP: h2#wsite-com-product-title, span[itemprop=price]@content, breadcrumbs.
Page family: PDP. Prices are GBP.
"""

import re

import scrapy


class ThelilyretreatImSpider(scrapy.Spider):
    name = "thelilyretreat_im"
    allowed_domains = ["thelilyretreatbeautyroom.co.uk", "www.thelilyretreatbeautyroom.co.uk"]
    base_url = "https://www.thelilyretreatbeautyroom.co.uk"
    currency = "GBP"
    language = "en"
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 2.0,
    }

    async def start(self):
        yield scrapy.Request(f"{self.base_url}/sitemap.xml", callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        seen = set()
        for loc in re.findall(r"<loc>([^<]+)</loc>", response.text):
            if re.search(r"/store/p\d+/", loc):
                url = loc.replace("http://", "https://")
                if url not in seen:
                    seen.add(url)
                    yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        name = " ".join(response.css("#wsite-com-product-title ::text").getall()).strip()
        price = response.css('span[itemprop="price"]::attr(content)').get()
        if not name or not price:
            return
        crumbs = [
            " ".join(c.css("::text").getall()).strip()
            for c in response.css("#wsite-com-breadcrumbs li.wsite-com-breadcrumb")
        ]
        crumbs = [c for c in crumbs if c]
        pid = re.search(r"/store/p(\d+)/", response.url)
        yield {
            "product_id": pid.group(1) if pid else None,
            "product_name": name,
            "price": price,
            "currency": self.currency,
            "category": crumbs[0] if crumbs else None,
            "url": response.url,
            "language": self.language,
            "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
        }
