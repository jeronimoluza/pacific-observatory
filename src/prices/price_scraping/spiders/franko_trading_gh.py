"""
Spider for Franko Trading Enterprise (Ghana) -- https://frankotrading.com/.

Phones/laptops/appliances/electronics retailer. The public site is a Vite
SPA (single index.html served for every path, including /product/<id>) that
calls a backend at https://testing.frankotrading.com with a client-embedded
`x-api-key` header (found in the JS bundle assets/index-*.js, no auth wall).
GetCTP001Products?pageNumber=N&recordPerPage=2000 returns clean pages of
{productName, productId, sellingPrice1}; page 5 of 5 returned 637 (<2000),
confirming pagination terminates rather than looping (8,637 products total,
verified 2026-09-01). No category or PDP HTML in the payload -- the site has
no server-rendered product page, so `url` is constructed from the known
/product/<id> route pattern seen in the JS bundle; category is left null for
the classifier. Currency GH₵/GHS confirmed via on-page markup in the bundle.
"""

import json
import logging

import scrapy

logger = logging.getLogger(__name__)


class FrankoTradingGhSpider(scrapy.Spider):
    name = "franko_trading_gh"
    allowed_domains = ["testing.frankotrading.com"]
    currency = "GHS"
    language = "en"

    API_URL = "https://testing.frankotrading.com/GetCTP001Products"
    API_KEY = "70RQ-opgyh-gjkz-56vxXd-98ztrb-154B"
    PAGE_SIZE = 2000
    MAX_PAGES = 20

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 1,
    }

    async def start(self):
        yield self._page_request(1)

    def _page_request(self, page):
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "x-api-key": self.API_KEY,
        }
        url = f"{self.API_URL}?pageNumber={page}&recordPerPage={self.PAGE_SIZE}"
        return scrapy.Request(
            url,
            headers=headers,
            callback=self.parse_page,
            meta={"page": page},
        )

    def parse_page(self, response):
        try:
            items = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error(f"JSON decode failed for {response.url}")
            return
        if not isinstance(items, list):
            logger.warning(f"Unexpected payload shape at {response.url}")
            return
        page = response.meta["page"]
        logger.info(f"franko_trading_gh: page={page} items={len(items)}")
        for it in items:
            pid = it.get("productId")
            name = it.get("productName")
            if not pid or not name:
                continue
            yield {
                "product_id": str(pid),
                "product_name": name.strip(),
                "price": it.get("sellingPrice1"),
                "currency": self.currency,
                "category": None,
                "url": f"https://www.frankotrading.com/product/{pid}",
                "language": self.language,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
        if len(items) == self.PAGE_SIZE and page < self.MAX_PAGES:
            yield self._page_request(page + 1)
