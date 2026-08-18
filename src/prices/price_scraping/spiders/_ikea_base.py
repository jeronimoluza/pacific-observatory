"""
Shared base class for IKEA storefront spiders.

IKEA runs the same market/language-path storefront (ikea.com/<market>/<lang>/)
across dozens of countries, backed by an open JSON search-and-listing service
at sik.search.blue.cdtapps.com. No auth, no WAF observed on this endpoint as
of 2026-08-07 (verified JP, KR, MY, TH, PH, AU).

Discovery: a single category-landing page (`/cat/products-products/`) embeds
IKEA's full mega-nav as plain `<a href="/<market>/<lang>/cat/<slug>-<key>/">`
links -- both top-level departments and their subcategories, ~200-300 per
market. The trailing dash-segment of each slug is the category `key` used by
the listing API. Parent and child category keys both appear in the nav;
querying both is safe (not just harmless) because the DuplicationPipeline
dedups on product URL (`pipUrl`), which is unique per SKU and appears
regardless of which category key surfaced it.

Listing endpoint (verified, no auth):
  https://sik.search.blue.cdtapps.com/<market>/<lang>/product-list-page
      ?category=<key>&size=<N>
No working offset/page parameter was found during onboarding (2026-08-07);
`size` alone returns the whole window when set above the category's true
count (largest observed: 651 items on fu002/JP), so a single generously-sized
request per category is used instead of pagination. Very large categories
may be truncated -- acceptable for onboarding, flagged here for anyone who
revisits pagination. The ae/sa markets (added 2026-08-07) reject size>1000
with a 400 ("Size parameter cannot exceed 1000") that JP/KR/MY/TH/PH/AU
never hit -- LISTING_SIZE is capped at 1000 accordingly, still well above
the largest observed category.

Price lives at item['salesPrice']['numeral'] + ['currencyCode'] -- use the
site's own currency, not a class-level assumption, since IKEA prices in
local currency per market and this has already burned other spiders
(tongamarket/niront) when hardcoded against countries.yaml defaults.

Subclasses set: name, allowed_domains, MARKET, LANG, currency, language.
Underscored filename -- Scrapy's SpiderLoader skips classes without `name`.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

CAT_HREF_RE = re.compile(
    r'href="(?:https://www\.ikea\.com)?(/[a-z]{2}/[a-z]{2}/cat/[a-z0-9-]+/)"'
)
LISTING_SIZE = 1000


class IkeaBaseSpider(scrapy.Spider):
    name = None
    MARKET: str = ""
    LANG: str = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 2,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        self.seen_ids = set()
        yield scrapy.Request(
            f"https://www.ikea.com/{self.MARKET}/{self.LANG}/cat/products-products/",
            callback=self.parse_nav,
        )

    def parse_nav(self, response):
        keys = set()
        for href in CAT_HREF_RE.findall(response.text):
            slug = href.rstrip("/").rsplit("/", 1)[-1]
            key = slug.rsplit("-", 1)[-1]
            if re.search(r"\d", key):
                keys.add(key)
        logger.info(f"{self.name}: {len(keys)} category keys discovered")
        for key in keys:
            yield scrapy.Request(
                f"https://sik.search.blue.cdtapps.com/{self.MARKET}/{self.LANG}/"
                f"product-list-page?category={key}&size={LISTING_SIZE}",
                callback=self.parse_category,
                meta={"category_key": key},
            )

    def parse_category(self, response):
        try:
            data = response.json()
        except ValueError:
            return
        plp = data.get("productListPage") or {}
        window = plp.get("productWindow") or []
        cat_name = (plp.get("category") or {}).get("name") or response.meta[
            "category_key"
        ]
        for item in window:
            product_id = item.get("id") or item.get("itemNo")
            if not product_id or product_id in self.seen_ids:
                continue
            price_block = item.get("salesPrice") or {}
            price = price_block.get("numeral")
            if price is None:
                continue
            self.seen_ids.add(product_id)

            name = item.get("mainImageAlt") or " ".join(
                filter(None, [item.get("name"), item.get("typeName")])
            )
            path = item.get("categoryPath") or []
            category = (
                " > ".join(c.get("name", "") for c in path[:3] if c.get("name"))
                or cat_name
            )
            url = item.get("pipUrl") or (
                f"https://www.ikea.com/{self.MARKET}/{self.LANG}/p/-{product_id}/"
            )

            yield {
                "product_id": str(product_id),
                "product_name": name[:500],
                "category": category,
                "price": str(price),
                "currency": price_block.get("currencyCode") or self.currency,
                "available": bool(item.get("onlineSellable", True)),
                "url": url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
