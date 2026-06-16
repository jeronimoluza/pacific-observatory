import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_PRICE_RE = re.compile(r'\\"finalPrice\\":(\d+)')
_ORIG_PRICE_RE = re.compile(r'\\"price\\":(\d+)')
_SKU_RE = re.compile(r'\\"skuCode\\":\\"([^\\]+)\\"')
_SKU_NAME_RE = re.compile(r'\\"skuName\\":\\"([^\\]+)\\"')
_SKU_SLUG_RE = re.compile(r'\\"skuSlug\\":\\"([^\\]+)\\"')
_NEXT_F_RE = re.compile(r"self\.__next_f\.push\(\[(.*?)\]\s*\)", re.DOTALL)

CATEGORY_ROOTS = [
    "https://fptshop.com.vn/dien-thoai",
    "https://fptshop.com.vn/may-tinh-xach-tay",
    "https://fptshop.com.vn/may-tinh-bang",
    "https://fptshop.com.vn/dong-ho-thong-minh",
    "https://fptshop.com.vn/tai-nghe",
    "https://fptshop.com.vn/may-anh",
]

_PRODUCT_SLUG_RE = re.compile(
    r'href="(/(?:dien-thoai|may-tinh-xach-tay|may-tinh-bang|dong-ho-thong-minh|tai-nghe|may-anh)/[a-z0-9-]+)"'
)
_CATEGORY_SLUG_RE = re.compile(
    r'href="(/(?:dien-thoai|may-tinh-xach-tay|may-tinh-bang|dong-ho-thong-minh|tai-nghe|may-anh)/[a-z0-9-]+)"'
)


class FptshopVNSpider(scrapy.Spider):
    name = "fptshop_vn"
    allowed_domains = ["fptshop.com.vn", "www.fptshop.com.vn"]
    currency = "VND"
    language = "vi"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.5,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
        "HTTPERROR_ALLOWED_CODES": [404, 410],
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scraped_skus = set()
        self.visited_categories = set()

    async def start(self):
        for url in CATEGORY_ROOTS:
            yield scrapy.Request(
                url,
                callback=self.parse_category,
                meta={"cat_url": url},
                errback=self.errback,
            )

    def parse_category(self, response):
        product_slugs = set(_PRODUCT_SLUG_RE.findall(response.text))
        emitted = 0
        for slug in product_slugs:
            url = urljoin("https://fptshop.com.vn", slug)
            if not any(
                slug.startswith(f"/{cat.split('/')[-1]}/") for cat in CATEGORY_ROOTS
            ):
                continue
            yield scrapy.Request(
                url,
                callback=self.parse_pdp,
                errback=self.errback,
            )
            emitted += 1
        logger.info(
            "category=%s products_queued=%d",
            response.meta["cat_url"],
            emitted,
        )

    def parse_pdp(self, response):
        text = response.text

        sku_codes = _SKU_RE.findall(text)
        sku_names = _SKU_NAME_RE.findall(text)
        final_prices = _PRICE_RE.findall(text)
        orig_prices = _ORIG_PRICE_RE.findall(text)
        sku_slugs = _SKU_SLUG_RE.findall(text)

        if not sku_codes or not final_prices:
            logger.warning("No SKU/price data on %s", response.url)
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        seen_in_page = set()
        for i, sku_code in enumerate(sku_codes):
            if sku_code in self.scraped_skus or sku_code in seen_in_page:
                continue
            seen_in_page.add(sku_code)
            self.scraped_skus.add(sku_code)

            price = (
                final_prices[i]
                if i < len(final_prices)
                else (orig_prices[i] if i < len(orig_prices) else None)
            )
            if not price:
                continue

            sku_name = sku_names[i] if i < len(sku_names) else sku_code
            sku_slug = sku_slugs[i] if i < len(sku_slugs) else None
            pdp_url = (
                urljoin("https://fptshop.com.vn", sku_slug)
                if sku_slug
                else response.url
            )

            category = (
                response.url.split("/")[3] if len(response.url.split("/")) > 3 else None
            )

            yield {
                "product_id": sku_code,
                "product_name": sku_name,
                "price": price,
                "currency": self.currency,
                "category": category,
                "url": pdp_url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

    def errback(self, failure):
        logger.error("Request failed: %s — %r", failure.request.url, failure.value)
