"""
Spider for Prom.ua (Ukraine) — prom.ua

Ukraine's largest general-merchandise marketplace. Category listing pages are
server-rendered (Tier 1A): each product block exposes stable `data-qaid` QA
hooks (the visible CSS class names are hashed and unstable, so we key off the
QA attributes). The final price sits in `data-qaprice` on the price node.

We crawl a few category landings spanning clothing/footwear (COICOP 03),
furniture/furnishings (05) and recreation goods — toys, sporting goods, books
(09). The catalogue is broad mixed merchandise, so COICOP is left to the
downstream Gemini classifier.

Only ~10 products are server-rendered per page (the rest lazy-load), so we walk
`?page=N`. product_id is the `pNNNN` token in the product URL.
"""

import logging
import re

import scrapy

logger = logging.getLogger(__name__)


class PromUaSpider(scrapy.Spider):
    name = "prom_ua"
    allowed_domains = ["prom.ua"]
    currency = "UAH"

    PAGES_PER_CATEGORY = 8  # ~10 SSR cards/page
    CATEGORIES = [
        ("Odezhda.html", "Одяг"),              # clothing       -> 03
        ("Obuv.html", "Взуття"),               # footwear       -> 03
        ("Mebel.html", "Меблі"),               # furniture      -> 05
        ("Igrushki.html", "Іграшки"),          # toys           -> 09
        ("Sport-i-otdyh.html", "Спорт"),       # sporting goods -> 09
        ("Knigi.html", "Книги"),               # books          -> 09
    ]
    _BASE = "https://prom.ua/{cat}?page={page}"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 1,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    _ID_RE = re.compile(r"/p(\d+)-")

    def start_requests(self):
        for cat, title in self.CATEGORIES:
            for page in range(1, self.PAGES_PER_CATEGORY + 1):
                yield scrapy.Request(
                    self._BASE.format(cat=cat, page=page),
                    callback=self.parse_listing,
                    meta={"category": title},
                )

    def parse_listing(self, response):
        blocks = response.css('div[data-qaid="product_block"]')
        category = response.meta.get("category")
        logger.info("prom_ua: %s -> %d blocks", response.url, len(blocks))
        for b in blocks:
            price = b.css('[data-qaid="product_price"]::attr(data-qaprice)').get()
            if not price:
                continue  # no price (out of stock / "price on request")
            name = (b.css('[data-qaid="product_name"]::text').get() or "").strip()
            href = b.css('a[data-qaid="product_link"]::attr(href)').get()
            if not name or not href:
                continue
            m = self._ID_RE.search(href)
            yield {
                "product_id": m.group(1) if m else None,
                "product_name": name,
                "price": price.strip(),
                "currency": self.currency,
                "category": category,
                "url": response.urljoin(href),
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
