"""Consumer electronics and solar products from Soukdarna, Chad."""

import re
from datetime import datetime, timezone

import scrapy


PRICE_RE = re.compile(r"([\d\s.\u00a0\u202f]+)\s*FCFA\b", re.I)


def parse_fcfa(text):
    match = PRICE_RE.search(text or "")
    if not match:
        return None
    digits = re.sub(r"\D", "", match.group(1))
    return digits or None


class SoukdarnaTdSpider(scrapy.Spider):
    name = "soukdarna_td"
    allowed_domains = ["soukdarna.com", "www.soukdarna.com"]
    start_urls = ["https://soukdarna.com/shop"]

    def parse(self, response):
        selectors = ".product, .product-card, article, [class*='product']"
        seen = set()
        for card in response.css(selectors):
            text = " ".join(t.strip() for t in card.css("::text").getall() if t.strip())
            price = parse_fcfa(text)
            name = (card.css("h2::text, h3::text, h4::text, h5::text").get() or "").strip()
            href = card.css("a::attr(href)").get()
            key = (name, price, href)
            if not name or price is None or key in seen:
                continue
            seen.add(key)
            yield {
                "product_name": name,
                "price": price,
                "currency": "XAF",
                "available": True,
                "url": response.urljoin(href) if href else response.url,
                "language": "fr",
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        for href in response.css('a[href*="page="], a.next::attr(href), a[rel="next"]::attr(href)').getall():
            yield response.follow(href, self.parse)
