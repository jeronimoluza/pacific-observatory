"""
Spider for Priceory Malaysia - https://www.priceory.com/
Third-party multi-store grocery price-comparison site (Next.js App Router,
but every route hit here is server-rendered plain HTML -- Tier 1A, no
Playwright needed at collection time; a Playwright network sniff on
/product/<id> found only Next.js RSC prefetch traffic, no separate JSON API).

Per the site's own /llms.txt: "Merchants commonly tracked (catalogue / flyer
sources): AEON, AEON BiG, 99 Speedmart, Lotus's, Jaya Grocer, Village
Grocer, Mydin, Econsave, Giant, NSK, TF Value Mart, KK Super Mart, Shopee
(quality-gated)". Ben's Independent Grocer is NOT in this list and does not
appear anywhere in the homepage/product RSC payload despite the
`?merchant=bens-independent-grocer` query param being accepted (verified:
that param produces no observable content change vs. no param at all --
dead/unrecognized filter, not a working per-merchant view). This is a
genuine multi-store comparison, not a thin skin over one merchant.

Prices are explicitly "catalogue / flyer figures, not a live cashier
guarantee" per the site itself -- still real per-SKU, per-outlet observed
prices (not a modeled/survey average), just sourced from retailer flyers
rather than live PDP scrapes.

No catalog-wide listing/pagination exists (/search requires a query and
does not paginate; /categories-style browsing does not exist). The site's
own /llms.txt names /staples and /brands as the "indexable main pages...
prefer these for discovery" -- so this spider crawls those two hub indexes,
follows every /staples/<slug> and /brands/<slug> page, and collects the
/product/<id> links found there.

Selectors verified against 6 live PDPs (2026-08-11), incl. multi-outlet
products (Village Grocer publishes distinct prices per physical outlet):
  ld+json Product block          -> name, sku, brand, offers.priceCurrency
  li.line-item (within the       -> one row per (store, outlet) offer
    .line-list panel)
    .merchant-inline-label::text -> store / outlet name
    .line-right strong::text     -> "RM X.XX" current price
    a.line-shop::attr(href)      -> retailer deep-link (used as item url --
                                     MUST be the per-row deep link, not the
                                     shared Priceory PDP url, or the
                                     run-wide url-dedup pipeline collapses
                                     every outlet's row into one)
    .line-meta::text             -> pack size (informational only)
Row count matches the ld+json offerCount exactly on every product checked
(11/11, 14/14, 16/16) -- no contamination from an unrelated "similar
products" block (only one `line-item` class family on the page).
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

PRICE_RE = re.compile(r"([0-9][0-9,]*\.[0-9]{2})")
LDJSON_RE = re.compile(
    r'<script type="application/ld\+json">\s*(\{.*?\})\s*</script>', re.S
)
SEED_URLS = [
    "https://www.priceory.com/staples",
    "https://www.priceory.com/brands",
]


class PriceoryMySpider(scrapy.Spider):
    name = "priceory_my"
    allowed_domains = ["priceory.com", "www.priceory.com"]
    currency = "MYR"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 8,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 4,
    }

    async def start(self):
        for url in SEED_URLS:
            yield scrapy.Request(url, callback=self.parse_index)

    def parse_index(self, response):
        hub_links = set(
            response.css('a[href^="/staples/"]::attr(href)').getall()
            + response.css('a[href^="/brands/"]::attr(href)').getall()
        )
        hub_links.discard("/staples")
        hub_links.discard("/brands")
        logger.info(f"priceory_my: {len(hub_links)} hub pages from {response.url}")
        for link in hub_links:
            yield response.follow(link, callback=self.parse_hub)

        for link in set(response.css('a[href^="/product/"]::attr(href)').getall()):
            yield response.follow(link, callback=self.parse_product)

    def parse_hub(self, response):
        product_links = set(response.css('a[href^="/product/"]::attr(href)').getall())
        logger.info(f"priceory_my: {len(product_links)} product urls at {response.url}")
        for link in product_links:
            yield response.follow(link, callback=self.parse_product)

    def parse_product(self, response):
        product_name = None
        sku = None
        currency = self.currency
        for block in LDJSON_RE.findall(response.text):
            try:
                data = json.loads(block)
            except json.JSONDecodeError:
                continue
            if data.get("@type") == "Product":
                product_name = data.get("name")
                sku = data.get("sku")
                currency = data.get("offers", {}).get("priceCurrency") or currency
                break

        if not product_name:
            product_name = response.css("h1::text").get()
        if not product_name:
            logger.debug(f"no product name found at {response.url}")
            return
        product_name = product_name.strip()[:500]

        if not sku:
            sku = response.url.rstrip("/").rsplit("/", 1)[-1]

        rows = response.css("li.line-item")
        if not rows:
            logger.debug(f"no line-item rows at {response.url}")
            return

        scraped_at = datetime.now(timezone.utc).isoformat()

        for row in rows:
            store = row.css(".merchant-inline-label::text").get()
            if not store:
                continue
            store = store.strip()

            price_text = row.css(".line-right strong::text").get()
            if not price_text:
                continue
            pm = PRICE_RE.search(price_text)
            if not pm:
                continue
            price = pm.group(1).replace(",", "")

            shop_url = row.css("a.line-shop::attr(href)").get() or response.url
            store_slug = re.sub(r"[^a-z0-9]+", "-", store.lower()).strip("-")

            yield {
                "product_id": f"{sku}__{store_slug}",
                "product_name": product_name,
                "category": None,
                "price": price,
                "currency": currency,
                "available": True,
                "url": shop_url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
