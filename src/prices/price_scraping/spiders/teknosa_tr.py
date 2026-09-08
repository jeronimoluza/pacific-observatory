"""
Spider for teknosa.com — Türkiye electronics big-box retailer.

Verified live 2026-09-06: server-rendered category pages (curl_cffi
chrome124, no headers, no Akamai/Cloudflare challenge encountered).
Category HTML embeds a per-page analytics data-layer JSON blob:

    "listing": {"items": [
        {"id": "100000063703-1001", "name": "...", "taxonomy": [...],
         "currency": "TRY", "unit_price": 187999.0,
         "unit_sale_price": 187999.0, "url": "https://www.teknosa.com/..."}
    ]}

extracted below via regex (id -> name -> ...taxonomy... -> currency ->
unit_price -> unit_sale_price -> url, in that fixed order) rather than a
full JSON parse, since the surrounding page is not valid standalone JSON.
`unit_sale_price` is what the customer actually pays (post-discount) and
is used as `price`; confirmed against a PDP fetch of one iphone listing —
its embedded `application/ld+json` Product/Offer block reported the same
TRY price, no minor-unit or discount-vs-list mismatch.

Category pagination is `?page=N` (0-indexed; confirmed page=0 and page=1
return disjoint majority-non-overlapping id sets — some sponsored/pinned
items repeat across pages, real catalog items do not). A fixed, small set
of broad top-level category slugs is walked (phones, computers/tablets,
white goods, home appliances, TVs) rather
than the full category tree, each capped at MAX_PAGES_PER_CATEGORY to
bound runtime — this is a general big-box catalog, not a food source, so
exhaustive category-tree discovery is not worth the crawl budget here.

coicop_classification left as classifier — wide electronics/appliance
catalog spans many COICOP leaves (05.x, 08.x, 09.x). channel:
electronics.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.teknosa.com"
MAX_PAGES_PER_CATEGORY = 15

CATEGORY_SLUGS = [
    "cep-telefonu-c-100001",
    "bilgisayar-tablet-c-116",
    "beyaz-esya-ankastre-c-103",
    "elektrikli-ev-aletleri-c-117",
    "televizyonlar-c-101001",
]

_ITEM_RE = re.compile(
    r'"id":\s*"([^"]+)",\s*"name":\s*"([^"]+)",.*?'
    r'"currency":\s*"([^"]+)",\s*"unit_price":([\d.]+),\s*'
    r'"unit_sale_price":([\d.]+),\s*"url":\s*"([^"]+)"',
    re.S,
)


class TeknosaTrSpider(scrapy.Spider):
    name = "teknosa_tr"
    allowed_domains = ["teknosa.com"]
    currency = "TRY"
    language = "tr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        for slug in CATEGORY_SLUGS:
            yield scrapy.Request(
                f"{BASE_URL}/{slug}?page=0",
                callback=self.parse_category,
                meta={"slug": slug, "page": 0},
            )

    def parse_category(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]
        matches = _ITEM_RE.findall(response.text)
        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for item_id, name, currency, unit_price, sale_price, url in matches:
            try:
                price_val = float(sale_price)
            except ValueError:
                continue
            if price_val <= 0:
                continue
            n += 1
            yield {
                "product_id": item_id,
                "product_name": name.strip()[:500],
                "category": slug,
                "price": str(price_val),
                "currency": currency or self.currency,
                "available": True,
                "url": url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"{self.name}: slug={slug} page={page} items={n}")
        if matches and page + 1 < MAX_PAGES_PER_CATEGORY:
            yield scrapy.Request(
                f"{BASE_URL}/{slug}?page={page + 1}",
                callback=self.parse_category,
                meta={"slug": slug, "page": page + 1},
            )
