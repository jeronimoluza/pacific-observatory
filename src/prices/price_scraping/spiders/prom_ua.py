"""
Spider for Prom.ua (Ukraine) — prom.ua

Ukraine's largest general-merchandise marketplace. Category listing pages expose
stable `data-qaid` QA hooks per product block (the visible CSS class names are
hashed and unstable, so we key off the QA attributes); the final price sits in
`data-qaprice` on the price node.

We crawl a few category landings spanning clothing/footwear (COICOP 03),
furniture/furnishings (05) and recreation goods — toys, sporting goods, books
(09). The catalogue is broad mixed merchandise, so COICOP is left to the
downstream Gemini classifier.

Only ~10 products are server-rendered per page; the rest lazy-load on scroll
(~59/page once fully scrolled). So this is a Tier-2 spider: each page is opened
in Playwright and scrolled to the bottom to hydrate the full grid before
parsing. product_id is the `pNNNN` token in the product URL.
"""

import logging
import re

import scrapy
from scrapy_playwright.page import PageMethod

logger = logging.getLogger(__name__)

# Scroll the listing to the bottom in steps so the lazy-loaded cards hydrate.
_SCROLL_METHODS = [
    PageMethod("wait_for_selector", '[data-qaid="product_block"]', timeout=30000),
]
for _frac in (0.25, 0.5, 0.75, 1.0, 1.0):
    _SCROLL_METHODS.append(
        PageMethod("evaluate", f"window.scrollTo(0, document.body.scrollHeight*{_frac})")
    )
    _SCROLL_METHODS.append(PageMethod("wait_for_timeout", 1500))


class PromUaSpider(scrapy.Spider):
    name = "prom_ua"
    allowed_domains = ["prom.ua"]
    currency = "UAH"

    PAGES_PER_CATEGORY = 5  # ~59 cards/page once scrolled
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
        "CONCURRENT_REQUESTS": 2,
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,
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
                    meta={
                        "category": title,
                        "playwright": True,
                        "playwright_page_goto_kwargs": {
                            "wait_until": "domcontentloaded"
                        },
                        "playwright_page_methods": _SCROLL_METHODS,
                    },
                    errback=self.errback,
                )

    def errback(self, failure):
        logger.error("prom_ua request failed: %s — %r",
                     failure.request.url, failure.value)

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
