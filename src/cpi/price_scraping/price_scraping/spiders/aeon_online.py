"""
Spider for scraping Aeon Online (Cambodia) - https://aeononlineshopping.com/

Site migrated from REST API (/api/store/{slug}) to Next.js App Router (RSC).
As of 2026-05, product data is embedded in the RSC payload of two page types:
  1. /shop-by-store   — lists all stores with ~8 products each (topSales)
  2. /shop-by-store/{slug} — individual store page with topSalesProducts (~12) and
     newArrivalProducts

Strategy:
  - Request /shop-by-store to get the full store list + inline products (120 items).
  - Then request each store's dedicated page to pick up topSalesProducts + newArrivalProducts.
  - Parse product data directly from self.__next_f.push RSC payloads (no Playwright needed —
    Next.js App Router server-renders the full RSC payload into the HTML).
"""

import re
import json
import logging
from datetime import datetime

import scrapy

logger = logging.getLogger(__name__)

# Regex to extract all RSC push payloads from HTML
_RSC_PUSH_RE = re.compile(r"self\.__next_f\.push\(\[(.*?)\]\)", re.DOTALL)


def _iter_rsc_json(html: str):
    """Yield decoded RSC payload strings from all __next_f.push() calls."""
    for m in _RSC_PUSH_RE.finditer(html):
        payload = m.group(1)
        # RSC pushes are JSON-encoded strings: 1,"..."
        str_match = re.match(r'^1,"(.*)"$', payload.strip(), re.DOTALL)
        if str_match:
            # Undo JSON string escaping applied by the server
            try:
                # Use json.loads to handle escape sequences correctly
                decoded = json.loads('"' + str_match.group(1) + '"')
                yield decoded
            except Exception:
                yield (
                    str_match.group(1)
                    .replace('\\"', '"')
                    .replace("\\n", "\n")
                    .replace("\\/", "/")
                )


class AeonOnlineSpider(scrapy.Spider):
    """
    Spider for Aeon Online (Cambodia).
    Scrapes product data from RSC payloads embedded in Next.js App Router pages.
    """

    name = "aeon_online"
    allowed_domains = ["aeononlineshopping.com"]
    country = "cambodia"
    currency = "KHR"

    # Landing page that lists all stores + has inline products in RSC payload
    SHOP_BY_STORE_URL = "https://aeononlineshopping.com/shop-by-store"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scraped_product_ids: set = set()

    def start_requests(self):
        yield scrapy.Request(
            self.SHOP_BY_STORE_URL,
            callback=self.parse_store_list,
            headers={"Accept": "text/html"},
        )

    # ------------------------------------------------------------------
    # Parse /shop-by-store — extract store list + inline products
    # ------------------------------------------------------------------

    def parse_store_list(self, response):
        scraped_at = datetime.utcnow().isoformat()
        store_slugs = []

        for decoded in _iter_rsc_json(response.text):
            # Each store block: "id":"aeon1-aeon-phnom-penh","name":"...","products":[...]
            # Store-level IDs are lowercase slugs (product IDs are numeric strings)
            slug_matches = re.findall(r'"id":"([a-z][a-z0-9-]+)"', decoded)
            for slug in slug_matches:
                if slug not in store_slugs:
                    store_slugs.append(slug)

            # Extract inline products for this payload segment
            # Pattern: {"id":"<numeric>","name":"...","price":"<digits>"}
            for prod_match in re.finditer(
                r'\{"id":"(\d+)","name":"([^"]+)","image":"[^"]*","price":"(\d+)"[^}]*\}',
                decoded,
            ):
                prod_id = prod_match.group(1)
                name = prod_match.group(2)
                price = prod_match.group(3)

                # Resolve store slug: look backwards for the nearest store id
                pos = prod_match.start()
                preceding = decoded[:pos]
                store_slug_m = re.findall(r'"id":"([a-z][a-z0-9-]+)"', preceding)
                store_slug = store_slug_m[-1] if store_slug_m else "unknown"

                if prod_id in self.scraped_product_ids:
                    continue
                self.scraped_product_ids.add(prod_id)

                yield {
                    "product_id": prod_id,
                    "product_name": name,
                    "price": price,
                    "currency": self.currency,
                    "store_slug": store_slug,
                    "category": "store-front",
                    "url": f"https://aeononlineshopping.com/product/{store_slug}/{prod_id}",
                    "scraped_at": scraped_at,
                }

        logger.info(
            "Found %d store slugs from /shop-by-store; scraped %d inline products so far",
            len(store_slugs),
            len(self.scraped_product_ids),
        )

        # Now request each individual store page for topSalesProducts + newArrivalProducts
        for slug in store_slugs:
            url = f"https://aeononlineshopping.com/shop-by-store/{slug}?tab=store-front"
            yield scrapy.Request(
                url,
                callback=self.parse_store_page,
                meta={"store_slug": slug},
                headers={"Accept": "text/html"},
            )

    # ------------------------------------------------------------------
    # Parse /shop-by-store/{slug} — topSalesProducts + newArrivalProducts
    # ------------------------------------------------------------------

    def parse_store_page(self, response):
        store_slug = response.meta.get("store_slug", "unknown")
        scraped_at = datetime.utcnow().isoformat()
        count = 0

        for decoded in _iter_rsc_json(response.text):
            # topSalesProducts and newArrivalProducts sections
            for section_key in ("topSalesProducts", "newArrivalProducts"):
                for prod_match in re.finditer(
                    r'"productId":(\d+),"image":"[^"]*","name":"([^"]+)","price":"(\d+)"',
                    decoded,
                ):
                    prod_id = prod_match.group(1)
                    name = prod_match.group(2)
                    price = prod_match.group(3)

                    if prod_id in self.scraped_product_ids:
                        continue
                    self.scraped_product_ids.add(prod_id)
                    count += 1

                    yield {
                        "product_id": prod_id,
                        "product_name": name,
                        "price": price,
                        "currency": self.currency,
                        "store_slug": store_slug,
                        "category": section_key,
                        "url": f"https://aeononlineshopping.com/product/{store_slug}/{prod_id}",
                        "scraped_at": scraped_at,
                    }

        logger.info(
            "Store %s: scraped %d new products from topSales/newArrival",
            store_slug,
            count,
        )
