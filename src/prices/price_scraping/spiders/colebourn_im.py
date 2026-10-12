"""
Spider for Colebourn (Isle of Man) - https://www.colebourn.com/
Douglas electrical and electronics retailer on a custom WordPress theme
(no WooCommerce Store API). Category listings render server-side product
cards (a.underline > span.title / span.price), paginated at /page/N/.
Page family: listing. Prices are GBP (the Isle of Man pound is at parity).
"""

import re

import scrapy


class ColebournImSpider(scrapy.Spider):
    name = "colebourn_im"
    allowed_domains = ["colebourn.com", "www.colebourn.com"]
    base_url = "https://www.colebourn.com"
    currency = "GBP"
    language = "en"
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 2.0,
    }

    async def start(self):
        yield scrapy.Request(
            f"{self.base_url}/product-category/computers/",
            callback=self.parse_home,
        )

    def parse_home(self, response):
        seen = set()
        for href in response.css('a[href*="/product-category/"]::attr(href)').getall():
            href = response.urljoin(href).split("?")[0].rstrip("/") + "/"
            if href.endswith("/feed/") or href in seen:
                continue
            seen.add(href)
            yield scrapy.Request(
                href,
                callback=self.parse_listing,
                meta={"category": href.rstrip("/").rsplit("/", 1)[-1], "page": 1, "base": href},
            )

    def parse_listing(self, response):
        category = response.meta["category"]
        cards = response.css("ul.products > li")
        scraped_at = response.headers.get("Date", b"").decode("utf-8")
        n = 0
        for card in cards:
            href = card.css("a::attr(href)").get()
            title = " ".join(card.css("span.title ::text").getall()).strip()
            price_txt = " ".join(card.css("span.price ::text").getall())
            m = re.search(r"([0-9][0-9,]*(?:\.[0-9]{1,2})?)", price_txt)
            if not (href and title and m):
                continue
            n += 1
            href = response.urljoin(href)
            yield {
                "product_id": href.rstrip("/").rsplit("/", 1)[-1],
                "product_name": title,
                "price": m.group(1).replace(",", ""),
                "currency": self.currency,
                "category": category,
                "url": href,
                "language": self.language,
                "scraped_at": scraped_at,
            }
        if n:
            page = response.meta["page"] + 1
            yield scrapy.Request(
                f"{response.meta['base']}page/{page}/",
                callback=self.parse_listing,
                meta={**response.meta, "page": page},
            )
