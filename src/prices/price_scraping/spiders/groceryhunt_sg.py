"""
Spider for GroceryHunt Singapore - https://groceryhunt.com/
Third-party price-comparison site (Laravel + Inertia/React front end, but
every route we hit is server-rendered plain HTML -- Tier 1A, no Playwright
needed). Each product page (/product/<slug>) renders a "Compare Prices"
table with one row per first-party retailer that stocks the item (observed:
Sheng Siong, Cold Storage, FairPrice -- all channel: supermarket). Product
catalog is enumerated via /search?page=N, which paginates the FULL catalog
when the query is empty (confirmed live: page 50 returns items, page 51
returns zero -- ~1,000 products total). Category listing pages
(/categories/<slug>) only ever return a fixed 30-item sample with no
pagination, so /search is the only way to reach the full catalog.

Selectors verified against 4 live PDPs (2026-08-11):
  h1                                          -> short item name
  h1's following sibling <div><span>...        -> [brand, size] badges
  table containing a <th>Store</th>            -> price-comparison table
    tbody tr .font-medium.text-gray-900::text  -> store name
    tbody tr td[1] .font-bold::text            -> current price ($X.XX)
    tbody tr a[target=_blank]::attr(href)      -> retailer deep-link (used
                                                   as item url -- MUST be
                                                   the per-store URL, not
                                                   the shared GroceryHunt
                                                   PDP url, or the run-wide
                                                   url-dedup pipeline
                                                   collapses all 3 stores'
                                                   rows into one)
  ld+json Product.category / .offers.priceCurrency -> category / currency
    (priceCurrency observed "SGD", matches countries.yaml; used when
    present, SGD class default otherwise)
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
MAX_SEARCH_PAGE = 200  # safety cap; real pagination stops itself first


class GroceryhuntSgSpider(scrapy.Spider):
    name = "groceryhunt_sg"
    allowed_domains = ["groceryhunt.com"]
    currency = "SGD"
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
        yield scrapy.Request(
            "https://groceryhunt.com/search?page=1",
            callback=self.parse_search,
            cb_kwargs={"page": 1},
        )

    def parse_search(self, response, page):
        links = response.css('a[href*="/product/"]::attr(href)').getall()
        product_urls = sorted(set(links))
        logger.info(f"groceryhunt_sg: page {page} -> {len(product_urls)} product urls")

        for url in product_urls:
            yield scrapy.Request(url, callback=self.parse_product)

        if product_urls and page < MAX_SEARCH_PAGE:
            yield scrapy.Request(
                f"https://groceryhunt.com/search?page={page + 1}",
                callback=self.parse_search,
                cb_kwargs={"page": page + 1},
            )

    def parse_product(self, response):
        name = response.css("h1::text").get()
        if not name:
            logger.debug(f"no name found at {response.url}")
            return
        name = name.strip()

        badges = response.xpath("//h1/following-sibling::div[1]/span/text()").getall()
        badges = [b.strip() for b in badges if b.strip()]
        brand = badges[0] if badges else None
        size = badges[1] if len(badges) > 1 else None
        full_name = " ".join(filter(None, [brand, name, size]))[:500]

        category = None
        currency = self.currency
        m = LDJSON_RE.search(response.text)
        if m:
            try:
                data = json.loads(m.group(1))
                category = data.get("category")
                currency = data.get("offers", {}).get("priceCurrency") or currency
            except (json.JSONDecodeError, AttributeError):
                pass

        price_table = response.xpath(
            '//table[.//th[contains(normalize-space(.), "Store")]]'
        )
        if not price_table:
            logger.debug(f"no price-comparison table at {response.url}")
            return

        slug = response.url.rstrip("/").rsplit("/", 1)[-1]
        scraped_at = datetime.now(timezone.utc).isoformat()

        for row in price_table.css("tbody tr"):
            store = row.css(".font-medium.text-gray-900::text").get()
            if not store:
                continue
            store = store.strip()

            cells = row.css("td")
            if len(cells) < 2:
                continue
            price_text = cells[1].css(".font-bold::text").get()
            if not price_text:
                continue
            pm = PRICE_RE.search(price_text)
            if not pm:
                continue
            price = pm.group(1).replace(",", "")

            store_url = row.css('a[target="_blank"]::attr(href)').get() or response.url
            store_slug = re.sub(r"[^a-z0-9]+", "-", store.lower()).strip("-")

            yield {
                "product_id": f"{slug}__{store_slug}",
                "product_name": full_name,
                "category": category,
                "price": price,
                "currency": currency,
                "available": True,
                "url": store_url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
