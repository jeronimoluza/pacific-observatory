"""Spider for CamHappyMart (Siem Reap, Cambodia), a 6valley-style PHP storefront.

Listing pages (/products?id=N&data_from=category&page=N) are server-rendered
with ~30 cards per page and rel="next" pagination; prices are USD. The JSON
API under /api/v1 requires auth, so this spider reads only public HTML.
Card titles are truncated server-side ("CAMBODIAN CHILI OIL 500..."), so each
new product gets one detail-page request for its full og:title. Subcategories
are swept before parents so products keep the most specific category, then
the data_from=latest listing picks up anything not in a category.
"""

import re
from datetime import datetime, timezone
from typing import Iterator

import scrapy


class CamhappymartKhSpider(scrapy.Spider):
    name = "camhappymart_kh"
    allowed_domains = ["camhappymart.com", "www.camhappymart.com"]
    base_url = "https://www.camhappymart.com"
    currency = "USD"
    language = "en"
    store_name = "CamHappyMart"

    custom_settings = {
        "CONCURRENT_REQUESTS": 1,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
        "USER_AGENT": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
        ),
    }

    _price_re = re.compile(r"\d[\d,]*(?:\.\d+)?")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_products = set()

    def _listing_url(self, category_id=None):
        if category_id is None:
            return f"{self.base_url}/products?data_from=latest&page=1"
        return f"{self.base_url}/products?id={category_id}&data_from=category&page=1"

    async def start(self):
        yield scrapy.Request(self._listing_url(), callback=self.parse_menu, priority=1000)

    def parse_menu(self, response):
        menu = response.css("ul.category-menu")[:1]
        for priority, links in (
            (20, menu.css(".mega_menu a")),
            (10, menu.xpath("./li/a")),
        ):
            for link in links:
                match = re.search(r"[?&]id=(\d+)", link.attrib.get("href", ""))
                name = " ".join("".join(link.css("::text").getall()).split())
                if match and name:
                    yield scrapy.Request(
                        self._listing_url(match.group(1)),
                        callback=self.parse_listing,
                        priority=priority,
                        meta={"category": name.lower(), "listing_priority": priority},
                    )
        yield response.request.replace(
            callback=self.parse_listing,
            priority=0,
            dont_filter=True,
            meta={"category": None, "listing_priority": 0},
        )

    def parse_listing(self, response):
        cards = response.css("div.product-single-hover")
        for card in cards:
            product_id = card.css("[data-product-id]::attr(data-product-id)").get()
            href = card.css(".single-product-details a::attr(href)").get()
            price_text = card.css(".product-price .text-accent::text").get()
            if not product_id or not href or not price_text or product_id in self.seen_products:
                continue
            match = self._price_re.search(price_text)
            if not match:
                continue
            self.seen_products.add(product_id)
            yield scrapy.Request(
                response.urljoin(href.split("?")[0]),
                callback=self.parse_product,
                priority=100,
                meta={
                    "product_id": product_id,
                    "price": match.group(0).replace(",", ""),
                    "category": response.meta["category"],
                },
            )

        next_href = response.css("ul.pagination a[rel=next]::attr(href)").get()
        if cards and next_href:
            yield response.follow(
                next_href,
                callback=self.parse_listing,
                priority=response.meta["listing_priority"],
                meta={
                    "category": response.meta["category"],
                    "listing_priority": response.meta["listing_priority"],
                },
            )

    def parse_product(self, response):
        name = response.css("meta[property='og:title']::attr(content)").get() or response.css(
            "title::text"
        ).get()
        if not name or not name.strip():
            return
        yield {
            "product_id": response.meta["product_id"],
            "product_name": " ".join(name.split()),
            "price": response.meta["price"],
            "currency": self.currency,
            "category": response.meta["category"],
            "url": response.url,
            "language": self.language,
            "store": self.store_name,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    # Common Crawl hook (prices/backfill.py and cc_weekly). The detail page has
    # no JSON-LD or price meta; the selling price is the
    # span.discounted_unit_price under the title (equal to the listing card
    # price, with del.total_unit_price as the pre-discount price when on sale).
    # Same markup in every capture sampled, 2025-03 through 2026-08.
    @classmethod
    def parse_html(cls, html_text: str, url: str) -> Iterator[dict]:
        sel = scrapy.Selector(text=html_text)
        name = sel.css("meta[property='og:title']::attr(content)").get() or sel.css(
            ".details span.__inline-24::text"
        ).get()
        price_text = sel.css("span.discounted_unit_price::text").get()
        match = cls._price_re.search(price_text or "")
        if not name or not name.strip() or not match:
            return
        yield {
            "product_id": sel.css("#add-to-cart-form input[name=id]::attr(value)").get(),
            "product_name": " ".join(name.split()),
            "price": match.group(0).replace(",", ""),
            "currency": cls.currency,
            "url": url,
            "language": cls.language,
            "store": cls.store_name,
        }
