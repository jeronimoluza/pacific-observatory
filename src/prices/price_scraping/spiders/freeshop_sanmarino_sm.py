"""FreeShop San Marino -- https://www.freeshop-sanmarino.sm/ (duty-free electronics and
household, Centro Atlante, 47891 San Marino).

Custom OpenCart (SEO URLs). Categories `/catalogo-prodotti/<a>[/<b>[/<c>]]`; listing cards are
`div.product-item` with `div.name a` (PDP `.../p/<sku>-<slug>`), `div.model` (SKU) and
`div.price` ("14,99€", tax-inclusive). Pagination `?limit=50&page=N`, stopped when a page adds no
new product. Page family: listing.
"""

import re
from datetime import datetime, timezone

import scrapy

_CAT_RE = re.compile(r'href="(https://www\.freeshop-sanmarino\.sm/catalogo-prodotti/[^"?#]+)"')
_PRICE_RE = re.compile(r"(\d[\d.]*,\d{2})\s*€")


class FreeshopSanmarinoSmSpider(scrapy.Spider):
    name = "freeshop_sanmarino_sm"
    allowed_domains = ["freeshop-sanmarino.sm"]
    currency = "EUR"
    language = "it"
    HOME = "https://www.freeshop-sanmarino.sm/"
    MAX_PAGES = 60

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.seen_cats: set[str] = set()
        self.seen_ids: set[str] = set()

    async def start(self):
        yield scrapy.Request(self.HOME, callback=self.parse_nav)

    def parse_nav(self, response):
        for url in _CAT_RE.findall(response.text):
            if url in self.seen_cats:
                continue
            self.seen_cats.add(url)
            yield scrapy.Request(
                f"{url}?limit=50&page=1",
                callback=self.parse_category,
                meta={"cat": url, "page": 1},
            )

    def parse_category(self, response):
        new = 0
        for card in response.css("div.product-item"):
            href = card.css("div.name a::attr(href)").get()
            name = card.css("div.name a::text").get()
            if not href or not name:
                continue
            m = re.search(r"/p/([^/?]+)$", href)
            pid = (card.css("div.model::text").get() or (m.group(1) if m else href)).strip()
            if pid in self.seen_ids:
                continue
            self.seen_ids.add(pid)
            new += 1
            ptxt = " ".join(card.css("div.price::text").getall())
            pm = _PRICE_RE.search(ptxt)
            if not pm:
                continue
            price = pm.group(1).replace(".", "").replace(",", ".")
            if float(price) <= 0:
                continue
            yield {
                "product_id": pid,
                "product_name": name.strip()[:500],
                "category": (response.css("h1::text").get() or "").strip() or None,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": href,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        page = response.meta["page"]
        if new and page < self.MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{response.meta['cat']}?limit=50&page={nxt}",
                callback=self.parse_category,
                meta={"cat": response.meta["cat"], "page": nxt},
            )
