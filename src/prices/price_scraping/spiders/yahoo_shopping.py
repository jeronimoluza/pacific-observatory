"""
Spider for scraping Yahoo Shopping (Japan) - https://shopping.yahoo.co.jp/
Extracts product information including prices, categories, and URLs.

Strategy:
1. Walk each top-level category via the paginating browse endpoint
   /category/{id}/list/?b={offset} (offset is a 1-based item index, ~30
   products per page). The /recommend endpoint used previously is a curated,
   non-paginating slice (~200 items/category) and is NOT used here.
2. Render each offset page with Playwright (the list is client-rendered) and
   extract name/price/url directly from the product cards.
3. Step the offset until a page yields no new products (Yahoo pins deep offsets
   to the last page) or MAX_OFFSET is reached.

Note: Yahoo Shopping has anti-bot protection on product pages, so we extract
data directly from listing pages where product cards show name, price, and URL.
"""

import scrapy
import logging
import re
from datetime import datetime, timezone
from scrapy_playwright.page import PageMethod

logger = logging.getLogger(__name__)


def _abort_heavy_requests(request) -> bool:
    """Best-effort: skip heavy assets to reduce timeouts."""
    resource_type = getattr(request, "resource_type", None)
    if resource_type in {"image", "media", "font", "stylesheet"}:
        return True

    url = getattr(request, "url", "") or ""
    return any(
        url.endswith(ext)
        for ext in (
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".webp",
            ".svg",
            ".woff",
            ".woff2",
            ".ttf",
            ".otf",
            ".css",
        )
    )


class YahooShoppingSpider(scrapy.Spider):
    """
    Spider for Yahoo Shopping (Japan).
    Walks each category's /list/?b={offset} browse pages with Playwright.
    """

    name = "yahoo_shopping"
    allowed_domains = ["shopping.yahoo.co.jp"]
    currency = "JPY"
    language = "jp"

    # Top-level category IDs to walk.
    CATEGORY_IDS = [
        # Food & Health
        ("2498", "食品"),
        ("2500", "ダイエット、健康"),
        ("2501", "コスメ、美容、ヘアケア"),
        # Fashion
        ("2494", "レディースファッション"),
        ("2495", "メンズファッション"),
        ("2496", "腕時計、アクセサリー"),
        # Kids & Baby
        ("2497", "ベビー、キッズ、マタニティ"),
        # Electronics
        ("2502", "スマートフォン、タブレット、パソコン"),
        ("2504", "テレビ、オーディオ、カメラ"),
        ("2505", "家電"),
        # Home & Living
        ("2506", "家具、インテリア"),
        ("2508", "キッチン、日用品、文具"),
        # Sports & Outdoor
        ("2512", "スポーツ"),
        ("2513", "アウトドア、釣り、旅行用品"),
    ]

    # Offset stepping. The page shows ~30 products; step below the smallest
    # observed page size so consecutive offsets overlap and never leave a gap.
    PAGE_STEP = 25
    # Yahoo pins deep offsets to the last page; the 0-new-products stop catches
    # that, this is just a hard safety bound.
    MAX_OFFSET = 6000

    # Product cards: the only div whose class carries the SearchResultItem
    # prefix and contains BOTH a product link and a price element is the row.
    ROW_XPATH = (
        '//div[contains(@class, "SearchResultItem__") '
        'and .//a[contains(@href, ".html")] '
        'and .//*[contains(@class, "ItemPrice_ItemPrice")]]'
    )

    custom_settings = {
        "PLAYWRIGHT_BROWSER_TYPE": "chromium",
        "PLAYWRIGHT_LAUNCH_OPTIONS": {
            "headless": True,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        },
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 120000,
        "PLAYWRIGHT_ABORT_REQUEST": _abort_heavy_requests,
        "DOWNLOAD_DELAY": 3,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "CONCURRENT_REQUESTS": 2,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scraped_product_ids = set()

    def _list_request(self, category_id, category_name, offset):
        url = f"https://shopping.yahoo.co.jp/category/{category_id}/list/?b={offset}"
        return scrapy.Request(
            url,
            callback=self.parse_listing,
            meta={
                "category_id": category_id,
                "category_name": category_name,
                "offset": offset,
                "playwright": True,
                "playwright_include_page": False,
                "playwright_page_goto_kwargs": {
                    # networkidle hangs on Yahoo (long-lived requests).
                    "wait_until": "domcontentloaded",
                },
                "playwright_page_methods": [
                    PageMethod("wait_for_timeout", 3500),
                ],
            },
            errback=self.errback_httpbin,
        )

    async def start(self):
        for category_id, category_name in self.CATEGORY_IDS:
            yield self._list_request(category_id, category_name, 1)

    def parse_listing(self, response):
        category_id = response.meta.get("category_id")
        category_name = response.meta.get("category_name")
        offset = response.meta.get("offset", 1)

        rows = response.xpath(self.ROW_XPATH)
        new_items = 0
        for row in rows:
            item = self._parse_row(row, category_name)
            if item:
                new_items += 1
                yield item

        logger.info(
            f"{category_name} b={offset}: {len(rows)} rows, {new_items} new "
            f"(total {len(self.scraped_product_ids)})"
        )

        # Continue while the page still surfaces unseen products. When Yahoo
        # pins the offset to the last page, every product is a duplicate and
        # new_items drops to 0, ending this category.
        if new_items > 0 and offset < self.MAX_OFFSET:
            yield self._list_request(
                category_id, category_name, offset + self.PAGE_STEP
            )

    def _parse_row(self, row, category_name):
        product_url = row.xpath('.//a[contains(@href, ".html")]/@href').get()
        product_name = (
            row.xpath('.//a[contains(@href, ".html")]//img/@alt').get()
            or row.xpath(
                './/span[contains(@class, "SearchResultItemTitle")]//text()'
            ).get()
        )

        price_text = "".join(
            row.css('[class*="SearchResultItem__price"] ::text').getall()
        )
        price = self._clean_price(price_text)

        if not (product_url and product_name and price):
            return None

        product_id = self._extract_product_id_from_url(product_url)
        # Dedup on the URL (always present); product_id can be None for store
        # domains the id regex doesn't recognise, and those must not leak dupes.
        dedup_key = product_id or product_url.split("?")[0]
        if dedup_key in self.scraped_product_ids:
            return None
        self.scraped_product_ids.add(dedup_key)

        return {
            "product_name": product_name.strip(),
            "category": category_name,
            "price": price,
            "currency": self.currency,
            "url": product_url,
            "product_id": product_id,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def _clean_price(self, price_str):
        """First yen amount in the price cell (ignores points/shipping text)."""
        if not price_str:
            return None
        match = re.search(r"([\d,]+)\s*円", price_str)
        if not match:
            match = re.search(r"[¥￥]\s?([\d,]+)", price_str)
        if match:
            return match.group(1).replace(",", "")
        return None

    def _extract_product_id_from_url(self, url):
        """
        Extract {store}_{item} id from a Yahoo Shopping product URL. Covers both
        store-front domains (.../{store}/{item}.html) and the /store/{s}/item/{i}
        layout used by lohaco/paypaymall.
        """
        match = re.search(r"yahoo\.co\.jp/store/([^/]+)/item/([^/?#]+)", url)
        if match:
            return f"{match.group(1)}_{match.group(2)}"

        match = re.search(
            r"\.yahoo\.co\.jp/([^/]+)/([^/?#]+?)(?:\.html)?(?:[?#]|$)", url
        )
        if match:
            return f"{match.group(1)}_{match.group(2)}"

        return None

    def errback_httpbin(self, failure):
        """Handle request failures."""
        logger.error(f"Request failed: {failure.request.url}")
