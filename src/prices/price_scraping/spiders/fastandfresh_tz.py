"""
Spider for Fast & Fresh (Tanzania) — https://www.fastandfresh.co.tz/.

Server-rendered catalog (custom Bootstrap storefront). The full catalog is
paginated at `/products?page=N`, 12 items/page, each card carrying name +
price directly in the HTML:
`<a href="product/lemon-grass" class="text-dark text-decoration-none">
Lemon Grass</a>...<span class="h5 mb-0 text-success price">TZS 1,000.00
</span>`. Paginate until a page returns zero product cards (confirmed
page=8 is empty for the current catalog size).

Re-verified live 2026-08-06: GET /products?page=1 -> 200, 77KB, 12 real
product cards incl. 'Lemon Grass' TZS 1,000.00, 'Chicken (Local)' TZS
23,000.00. Currency TZS matches countries.yaml. Per-kg/per-unit pricing on
produce/meat/eggs per prior research.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.fastandfresh.co.tz"
_CARD_RE = re.compile(
    r'<a href="(product/[a-z0-9-]+)" class="text-dark text-decoration-none">\s*'
    r"([^<]+?)\s*</a>.*?"
    r'class="[^"]*\bprice\b[^"]*">TZS\s*([\d,]+\.\d{2})</span>',
    re.S,
)
MAX_PAGES = 100  # safety cap


class FastandfreshTzSpider(scrapy.Spider):
    name = "fastandfresh_tz"
    allowed_domains = ["fastandfresh.co.tz"]
    currency = "TZS"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(
            f"{_BASE}/products?page=1",
            callback=self.parse_page,
            meta={"page": 1},
        )

    def parse_page(self, response):
        page = response.meta["page"]
        cards = _CARD_RE.findall(response.text)
        logger.info(f"fastandfresh_tz page={page} count={len(cards)}")
        if not cards:
            return
        scraped_at = datetime.now(timezone.utc).isoformat()
        for url_path, name, price in cards:
            yield {
                "product_id": url_path.split("/", 1)[-1],
                "product_name": name.strip()[:500],
                "category": None,
                "price": price.replace(",", ""),
                "currency": self.currency,
                "available": True,
                "url": f"{_BASE}/{url_path}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        if page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{_BASE}/products?page={nxt}",
                callback=self.parse_page,
                meta={"page": nxt},
            )
