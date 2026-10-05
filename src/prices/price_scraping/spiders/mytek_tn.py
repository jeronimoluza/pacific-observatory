"""Electronics and household catalogue from Mytek Tunisia."""

import re
from datetime import datetime, timezone

import scrapy


PRICE_RE = re.compile(r"([\d\s\u00a0\u202f]+(?:[.,]\d{3})?)\s*DT\b", re.I)


def parse_tnd(text):
    match = PRICE_RE.search(text or "")
    if not match:
        return None
    value = re.sub(r"[\s\u00a0\u202f]", "", match.group(1)).replace(",", ".")
    return value


class MytekTnSpider(scrapy.Spider):
    name = "mytek_tn"
    allowed_domains = ["mytek.tn", "www.mytek.tn"]
    start_urls = ["https://www.mytek.tn/informatique/ordinateur-de-bureau.html"]

    def parse(self, response):
        for card in response.css("li.product-item, .product-item-info"):
            name = (card.css("a.product-item-link::text, .product-item-name a::text").get() or "").strip()
            href = card.css("a.product-item-link::attr(href), .product-item-name a::attr(href)").get()
            price_text = " ".join(card.css(".price::text").getall())
            price = parse_tnd(price_text)
            if name and price:
                yield {
                    "product_name": name,
                    "price": price,
                    "currency": "TND",
                    "available": "epuisé" not in " ".join(card.css("::text").getall()).lower(),
                    "url": response.urljoin(href) if href else response.url,
                    "language": "fr",
                    "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
                }

        next_url = response.css("a.action.next::attr(href), a[rel='next']::attr(href)").get()
        if next_url:
            yield response.follow(next_url, self.parse)
