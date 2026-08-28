"""
Spider for Komus (Russia) — national office/household/workwear retailer.

URL discovery via /sitemap.xml -> /sitemap/N.xml (33 chunks, ~10k URLs each,
product URLs match /katalog/.../p/<id>/). Product pages are server-rendered
with Schema.org Product microdata (meta itemprop="price"/"priceCurrency"/
"availability", brand) but the product title itself is Vue-hydrated client
side with no server-rendered <h1> or itemprop="name" -- the title is instead
recovered from the always-present og:title meta tag, which carries the clean
name before a " - купить..." marketing suffix.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

SITEMAP_INDEX_URL = "https://www.komus.ru/sitemap.xml"
_ID_RE = re.compile(r"/p/(\d+)")
_TITLE_SUFFIX_RE = re.compile(r"\s*[–—-]?\s*купить по выгодной цене.*$", re.IGNORECASE)
# Under sustained load/503 retries, some requests land on a "reviews" tab variant
# of the product page (url gains /otzyvy/?tabId=reviews via redirect) whose
# og:title is "Отзывы на <name> – мнения покупателей на KOMUS.ru, ..." instead
# of the normal "<name> купить по выгодной цене..." title. Price/currency
# microdata still resolves correctly on that variant, only the title differs.
_REVIEWS_TITLE_RE = re.compile(
    r"^\s*Отзывы на\s+(.*?)\s*[–—-]\s*мнения покупателей.*$", re.IGNORECASE
)


class KomusRuSpider(scrapy.Spider):
    name = "komus_ru"
    allowed_domains = ["komus.ru", "www.komus.ru"]
    currency = "RUB"
    language = "ru"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 8,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(
            SITEMAP_INDEX_URL,
            callback=self.parse_sitemap_index,
            errback=self.errback,
        )

    def parse_sitemap_index(self, response):
        sitemap_urls = response.xpath("//*[local-name()='loc']/text()").getall()
        logger.info(f"sitemap index: {len(sitemap_urls)} sub-sitemaps")
        for url in sitemap_urls:
            yield scrapy.Request(url, callback=self.parse_sitemap, errback=self.errback)

    def parse_sitemap(self, response):
        urls = response.xpath("//*[local-name()='loc']/text()").getall()
        product_urls = [u for u in urls if "/p/" in u]
        logger.info(
            f"{response.url}: {len(urls)} urls total, queued {len(product_urls)} products"
        )
        for url in product_urls:
            yield scrapy.Request(url, callback=self.parse_product, errback=self.errback)

    def parse_product(self, response):
        price = response.xpath('//meta[@itemprop="price"]/@content').get()
        if not price:
            logger.warning(f"no price microdata at {response.url}")
            return
        currency = (
            response.xpath('//meta[@itemprop="priceCurrency"]/@content').get()
            or self.currency
        )
        og_title = response.xpath('//meta[@property="og:title"]/@content').get()
        if not og_title:
            logger.warning(f"no og:title at {response.url}")
            return
        review_match = _REVIEWS_TITLE_RE.match(og_title)
        name = (
            review_match.group(1).strip()
            if review_match
            else _TITLE_SUFFIX_RE.sub("", og_title).strip()
        )
        if not name:
            return
        brand = response.xpath(
            '//*[@itemprop="brand"]//*[@itemprop="name"]/text()'
        ).get()
        availability = (
            response.xpath('//meta[@itemprop="availability"]/@content').get() or ""
        )
        m = _ID_RE.search(response.url)
        product_id = m.group(1) if m else response.url

        yield {
            "product_id": product_id,
            "product_name": name[:500],
            "brand": brand,
            "category": None,
            "price": str(price),
            "currency": currency,
            "available": "InStock" in availability,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def errback(self, failure):
        logger.error(f"Request failed: {failure.request.url} — {failure.value!r}")
