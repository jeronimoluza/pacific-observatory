"""
Spider for Rakuten category landing pages - https://www.rakuten.co.jp/category/

Uses scrapy-impersonate with a desktop Safari TLS fingerprint. Chrome/Edge
profiles get HTTP 403 from Rakuten's anti-bot; Safari profiles pass through.
The category landing pages embed ~52 featured products as `div.dui-card`
elements with structured `data-track-*` attributes — no JS rendering needed.
Pagination on the /category/ endpoint is a no-op (every page returns the
same 52 cards) and the /search/mall/-/ endpoint 301s for non-curl clients,
so we collect one page per category.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

import scrapy

logger = logging.getLogger(__name__)

# Category IDs live in an adjacent TSV (`<id>\t<name>` per line) discovered by
# crawling https://www.rakuten.co.jp/category/. Storing inline would push this
# file past the 500-line cap.
CATEGORIES_FILE = Path(__file__).parent / "rakuten_categories.tsv"


def _load_categories() -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for line in CATEGORIES_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        cat_id, name = parts[0].strip(), parts[1].strip()
        if cat_id and name:
            pairs.append((cat_id, name))
    return pairs


class RakutenSpider(scrapy.Spider):
    name = "rakuten"
    allowed_domains = ["www.rakuten.co.jp"]
    currency = "JPY"
    language = "jp"

    CATEGORY_IDS = _load_categories()

    IMPERSONATE_PROFILE = "safari17_0"

    # Disable project-level RandomBrowserMiddleware and CustomUserAgentMiddleware:
    # both overwrite request state (impersonate profile, UA header), and Rakuten
    # 403s on Chrome TLS fingerprints. Letting curl_cffi's safari profile set its
    # own UA is what passes the anti-bot check.
    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
            "price_scraping.middlewares.CustomUserAgentMiddleware": None,
        },
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scraped_product_ids: set[str] = set()

    def start_requests(self):
        for category_id, category_name in self.CATEGORY_IDS:
            yield scrapy.Request(
                f"https://www.rakuten.co.jp/category/{category_id}/",
                callback=self.parse_category,
                meta={
                    "impersonate": self.IMPERSONATE_PROFILE,
                    "category_id": category_id,
                    "category_name": category_name,
                },
                errback=self.errback,
            )

    def parse_category(self, response):
        category_id = response.meta["category_id"]
        category_name = response.meta["category_name"]

        cards = response.css("div.dui-card[data-track-itemid]")
        items_yielded = 0
        scraped_at = datetime.now(timezone.utc).isoformat()

        for card in cards:
            item_id = card.attrib.get("data-track-itemid")
            price = card.attrib.get("data-track-price")
            name = card.css("img::attr(alt)").get()

            if not (item_id and price and name):
                continue

            product_id = item_id.replace("/", "_")
            if product_id in self.scraped_product_ids:
                continue
            self.scraped_product_ids.add(product_id)

            yield {
                "product_id": product_id,
                "product_name": name.strip()[:500],
                "category": category_name,
                "price": price,
                "currency": self.currency,
                "url": f"https://item.rakuten.co.jp/{item_id}/",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
            items_yielded += 1

        logger.info(
            f"category={category_name} cards={len(cards)} items={items_yielded}"
        )

    def errback(self, failure):
        logger.error(f"Request failed: {failure.request.url} — {failure.value!r}")
