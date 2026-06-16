"""
Spider for City Mall Online (Myanmar) — https://www.citymall.com.mm/

scrapy-impersonate with safari17_0 (Playwright is detected and blocked).

The site is built on SAP Hybris. The standard category-landing URL
(/citymall/my/c/<id>) renders no product cards — products are returned only by
the search endpoint /citymall/my/search?q=:category:<code>&page=N.

Strategy:
  1. Walk sitemap.xml -> CategoryLanding-my-MMK*.xml for 115 authoritative
     category codes.
  2. For each code, page through &page=N until a page returns zero SKUs.
  3. Each card (div.card.product-listing) exposes SKU, name, price, PDP URL
     in static HTML.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

SITEMAP_INDEX = "https://www.citymall.com.mm/citymall/my/sitemap.xml"
CATEGORY_LANDING_SM = re.compile(r"CategoryLanding-my-")
CAT_CODE_RE = re.compile(r"/c/([A-Za-z0-9_]+)$")
PRICE_RE = re.compile(r"([\d,]+)\s*Ks")


class CitymallMmSpider(scrapy.Spider):
    name = "citymall_mm"
    allowed_domains = [
        "citymall.com.mm",
        "www.citymall.com.mm",
        "cmhlprodblobstorage1.blob.core.windows.net",
    ]
    currency = "MMK"
    language = "my"

    IMPERSONATE_PROFILE = "safari17_0"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
            "price_scraping.middlewares.CustomUserAgentMiddleware": None,
        },
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
        "CONCURRENT_REQUESTS": 16,
        "DOWNLOAD_DELAY": 0.1,
        "RETRY_TIMES": 3,
        "DOWNLOAD_TIMEOUT": 60,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scraped_skus: set[str] = set()

    async def start(self):
        yield scrapy.Request(
            SITEMAP_INDEX,
            callback=self.parse_sitemap_index,
            meta={"impersonate": self.IMPERSONATE_PROFILE},
            errback=self.errback,
        )

    def parse_sitemap_index(self, response):
        locs = response.xpath("//*[local-name()='loc']/text()").getall()
        cat_landing_sms = [u for u in locs if CATEGORY_LANDING_SM.search(u)]
        logger.info(
            f"sitemap index: {len(locs)} sub-sitemaps, {len(cat_landing_sms)} category landings"
        )
        for url in cat_landing_sms:
            yield scrapy.Request(
                url,
                callback=self.parse_category_sitemap,
                meta={"impersonate": self.IMPERSONATE_PROFILE},
                errback=self.errback,
            )

    def parse_category_sitemap(self, response):
        urls = response.xpath("//*[local-name()='loc']/text()").getall()
        codes: list[str] = []
        for u in urls:
            m = CAT_CODE_RE.search(u.rstrip("/"))
            if m:
                codes.append(m.group(1))
        logger.info(f"category sitemap: {len(codes)} codes from {response.url[-80:]}")
        for code in codes:
            yield self._search_request(code, 0)

    def _search_request(self, code: str, page: int) -> scrapy.Request:
        url = (
            f"https://www.citymall.com.mm/citymall/my/search"
            f"?q=:category:{code}&page={page}"
        )
        return scrapy.Request(
            url,
            callback=self.parse_search,
            meta={
                "impersonate": self.IMPERSONATE_PROFILE,
                "category_code": code,
                "page": page,
            },
            errback=self.errback,
        )

    def parse_search(self, response):
        code = response.meta["category_code"]
        page = response.meta["page"]

        cards = response.css("div.card.product-listing")
        items_yielded = 0
        new_skus = 0
        scraped_at = datetime.now(timezone.utc).isoformat()

        for card in cards:
            sku = card.css("input[name='productCodePost']::attr(value)").get()
            if not sku:
                continue
            name = card.css("a.name::text").get() or ""
            href = card.css("a.name::attr(href)").get()
            price_text = card.css("p.product-price::text").get() or ""
            m = PRICE_RE.search(price_text)
            if not (name.strip() and m):
                continue
            if sku in self.scraped_skus:
                continue
            self.scraped_skus.add(sku)
            new_skus += 1
            items_yielded += 1
            yield {
                "product_id": sku,
                "product_name": name.strip()[:500],
                "category": code,
                "price": m.group(1).replace(",", ""),
                "currency": self.currency,
                "url": response.urljoin(href) if href else response.url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        logger.info(
            f"category={code} page={page} cards={len(cards)} new_skus={new_skus}"
        )

        # Continue paginating while at least one card was returned. Stop on
        # empty page (out-of-range) or when the page yielded only duplicates.
        if cards and new_skus > 0:
            yield self._search_request(code, page + 1)

    def errback(self, failure):
        logger.error(f"Request failed: {failure.request.url} — {failure.value!r}")
