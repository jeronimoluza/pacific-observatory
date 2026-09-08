"""
Greens Supermarket (Malta) — https://greens.com.mt/.

Shard AI_NOTES guessed WooCommerce; that is wrong. The storefront is a
"Krystal CMS" ASP.NET WebForms build, and /wp-json/wc/store/v1/products
does not exist (it falls through to the SPA shell, HTML not JSON).

The real backend is a bearer-token-guarded JSON API:

    GET /apiservices/retail/sync/productlist?Agent=GREENS&Loc=SM&...
        &Category=<cat>&NumberOfRecords=<n>&page=<n>...

The bearer token is NOT fetched via a separate auth call — it is rendered
directly into each category page's inline `getProductList('<token>', ...)`
call, so one plain GET (no Playwright) is enough to mint a token, and that
token works cookie-free against the API from a completely different HTTP
session (verified). Must hit the `www.` host — the bare-domain host serves
a redirect-free but token-invalid variant (`www` in cookies/CSRF scope).

One request per top-level category (NumberOfRecords=500 comfortably covers
every category's total — the largest observed was 276) rather than paging;
a plain page=1 request already returns TOTAL_RECORDS, and every category
seen so far fits in one page at that size.

Currency EUR (Malta, matches countries.yaml). Prices are plain decimals
(SALES_PRICE), no minor-unit division needed.

Verified live 2026-09-06: Butcher category alone returned 276 real SKUs
(e.g. "Affumicato Sausage" EUR 14.00, "7days Bake Roll Sour Cream Onion
150g" from Bakery). GROUP_1..GROUP_3 fields give a 3-level breadcrumb.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE = "https://www.greens.com.mt"
_TOKEN_RE = re.compile(r"getProductList\('([^']+)'")

# Top-level categories enumerated from the homepage nav (proper-cased;
# lowercase duplicates in the nav markup alias the same category).
CATEGORIES = [
    "Baby",
    "Bakery",
    "Beverages",
    "Butcher",
    "CheeseCounter",
    "ChilledAndDairy",
    "CondimentsAndSeasoning",
    "Confectionery",
    "Cosmetics",
    "Delicatessen",
    "Fish",
    "FlowersAndPlants",
    "FrozenFoods",
    "Fruits",
    "FruitsAndVegetables",
    "Groceries",
    "Health",
    "HomeGarden",
    "Household",
    "New",
    "PersonalCare",
    "Pets",
    "WineCellar",
]

PER_PAGE = 2000


class GreensMtSpider(scrapy.Spider):
    name = "greens_mt"
    allowed_domains = ["greens.com.mt"]
    currency = "EUR"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        # Any category page carries a valid token; use the first category.
        yield scrapy.Request(
            f"{BASE}/products?cat={CATEGORIES[0]}",
            callback=self.parse_token_page,
            errback=self.errback,
        )

    def parse_token_page(self, response):
        match = _TOKEN_RE.search(response.text)
        if not match:
            logger.error(f"{self.name}: no bearer token found on {response.url}")
            return
        token = match.group(1)
        logger.info(f"{self.name}: token acquired")
        for cat in CATEGORIES:
            yield self._api_request(cat, token)

    def _api_request(self, category, token):
        url = (
            f"{BASE}/apiservices/retail/sync/productlist"
            f"?Agent=GREENS&Loc=SM&Eid=N/A&SearchCriteria="
            f"&page=1&NumberOfRecords={PER_PAGE}"
            f"&SortType=Position&SortDirection=Asc"
            f"&Category={category}&Category2=&Category3=&Type="
            f"&Cid=00000000-0000-0000-0000-000000000000"
            f"&Cart=00000000-0000-0000-0000-000000000000"
            f"&SubType=&Brand=&ProductListType=products"
            f"&Mobdev=False&Detailed=True"
        )
        return scrapy.Request(
            url,
            callback=self.parse_api,
            errback=self.errback,
            headers={
                "Authorization": f"Bearer {token}",
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json",
                "Referer": f"{BASE}/products?cat={category}",
            },
            meta={"category": category},
            dont_filter=True,
        )

    def parse_api(self, response):
        category = response.meta["category"]
        try:
            payload = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON from {response.url}")
            return
        products = payload.get("ProductList") or []
        found = 0
        for entry in products:
            d = entry.get("ProductDetails") or {}
            name = (d.get("PART_DESCRIPTION") or "").strip()
            pid = d.get("PART_NUMBER")
            price = d.get("SALES_PRICE")
            if not name or pid is None or price in (None, 0):
                continue
            breadcrumb = " > ".join(
                str(d.get(k)) for k in ("GROUP_1", "GROUP_2", "GROUP_3") if d.get(k)
            )
            found += 1
            yield {
                "product_id": str(pid),
                "product_name": name[:500],
                "category": breadcrumb or category,
                "price": str(price),
                "currency": self.currency,
                "available": d.get("SYSTEM_STATUS") == "A",
                "url": f"{BASE}/productdetails?pid={pid}",
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        total = products[0]["ProductDetails"].get("TOTAL_RECORDS") if products else 0
        logger.info(
            f"{self.name}: category={category} yielded={found} total_reported={total}"
        )

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
