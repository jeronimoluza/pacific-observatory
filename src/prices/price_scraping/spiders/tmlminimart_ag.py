"""
TML Mini Mart (Antigua and Barbuda) — vendor storefront on AllMart
(https://www.allmartplace.com/), Antigua's local delivery/pickup
marketplace app.

BACKGROUND: Antigua had no channel:supermarket/hypermarket/fresh-market
source. CaribeEats (the OTHER Caribbean delivery aggregator, already
checked per the onboarding brief) has only 8 Antigua businesses, none a
real grocery. AllMart is a DIFFERENT, genuinely local platform ("AllMart -
Local Marketplace, Cassada Gardens, Antigua and Barbuda"; WhatsApp support
+1 268 713 0040; "150+ local merchants" per its own app-store listing;
Jungleworks "Yelo" white-label backend, confirmed via the customer
webapp's JS bundle referencing yelo.red infrastructure domains) that DOES
carry real grocery businesses among its ~158 storefronts (confirmed via
/api/marketplace/marketplace_get_city_storefronts_v3, cleanly paginated —
skip=0/50/100/150 returned disjoint id sets, 158 distinct total). TML Mini
Mart (business id 1589747) is one of the food-heaviest of those: the
platform itself tags it custom_tag_for_merchant="GROCERY",
business_categories_name="Groceries,Home & Decor", with a physical address
"Sir George Walter Highway, Osbourn, Saint George, Antigua, Antigua and
Barbuda" (read directly from the storefronts payload, not inferred).

A larger AllMart grocery vendor, "gourmet-basket" (Gourmet Basket
Supermarket, business id 1402365, 15 top-level categories: Produce,
Grocery, Meat & Seafood, Bakery, Dairy & Eggs, ...), was found but SKIPPED
as a near-duplicate of the already-onboarded islandprovision_ag.yaml,
whose notes record Gourmet Basket Supermarket as one of Island Provision
Group's four in-house divisions on the same islandprovision.com WooCommerce
catalog — building it again here would double-count the same retailer.

PLATFORM / ACCESS: the AllMart web app (allmartplace.com) sits behind
Cloudflare with a Turnstile challenge that blocks headless-Chromium
rendering of the Angular SPA shell (confirmed: Playwright hits
challenges.cloudflare.com/turnstile before the store list ever paints, and
the rendered DOM body stays ~80 chars of chrome with no store cards even
after a 20s wait with stealth args and geolocation permission granted).
BUT the JSON API endpoints themselves are NOT behind that challenge: every
endpoint below returns clean 200 JSON to a plain curl_cffi GET
(impersonate="chrome124"), no cookies, no session, no captcha — this is
the repo's documented "Playwright/browser to discover, plain HTTP to
scrape" pattern, just with the discovery half done by downloading and
grepping the SPA's Angular bundle (main.js) and all 69 lazy-loaded route
chunks (chunk hash manifest lives inline in runtime.js) for the
CatalogueService method bodies, since Playwright network-capture could
not get far enough past the Turnstile wall to observe real traffic.

API shape (all GET; `post_to_get=1` is a real, load-bearing param that
tells the backend to treat the querystring as a virtual POST body — not
cargo-culted):
  - /api/get_app_catalogue?user_id=<vendor>&marketplace_user_id=...
        -> this vendor's top-level category tree (one level only).
  - /api/catalogue/get?parent_category_id=<id>&user_id=<vendor>&...
        -> children of one category. NOT `menu_id` — that field exists on
           the same client-side method but is a vestigial/unrelated param
           used only by menu-enabled restaurant tenants; this vendor has
           is_menu_enabled=0 and only responds to parent_category_id
           (confirmed: menu_id alone returns the top-level list again,
           unchanged; parent_category_id drills down correctly).
  - /api/get_products_for_category?parent_category_id=<leaf_id>&offset=
        &limit=&page_no=&date_time=<ISO8601>&...
        -> paginated product list for one leaf category. Needs
           parent_category_id (not menu_id) for the same reason as above.

Category tree: 52 leaf categories (has_children=0, has_products=1) under
9 top-level nodes. Food-relevant: "Groceries" (12 subcats — Nuts & Seeds,
Cereals, Noodles/Macaroni/Spaghetti, Soup Mix, Canned Goods, Milk/
Flour/Seasonings, Rice/Sugar/Salt, Sauces & Dressings, Vinegar & Oils,
Chocolate & Sweet Treats, Crackers & Biscuits, Snacks & Gums), "Middle
Eastern Groceries" (Nuts & Seeds, Coffee & Tea, Cookies & Chocolate,
Canned & Jarred Goods, Oils & Sauces, Air Fresheners), "Drinks" (Energy
Drinks, Canned Drinks, Solo Soda/Ting/Tropical Delight, Box Juice, Water,
Refrigerated Drinks, Malts & Beers, Liquor & Wines — non-alcoholic AND
alcoholic). Tobacco: Vapes/Vapes+/Cigarettes & Cigars/Lighters.../
Hookahs*. The rest (Household Items, Hygiene Products) is non-food and
will classify outside 01/02, same as any real mini-mart's mixed catalog.

Verified enumerable at probe time: page1 (offset=0) vs page2 (offset=25)
returned ZERO product_id overlap on every leaf that had more than 25
products (e.g. "Refrigerated Drinks" 25+25 disjoint, "Vapes" 25+18
disjoint). Sampling just the first two pages of all 52 leaves already
totalled ~800 distinct products; the crawl below walks every page per
leaf (not just two), so the true catalogue is at least that large.

Currency: MEASURED, not inferred. Each product's own `layout_data.lines`
field carries the platform's own rendered price string, e.g. "EC$13.00"
for product_id 108831831 "Grace Corned Beef" (price field = 13, a plain
decimal in major units — NOT minor-unit cents). "EC$" is the unambiguous
Eastern Caribbean Dollar symbol, distinct from the generic "$" the
onboarding brief warns is ambiguous across Caribbean currencies.

No per-product web page exists (app-only PDP, same limitation as the
CaribeEats platform's _caribeeats_base.py) — DuplicationPipeline dedups on
item['url'], so a synthetic per-product URL is built as the vendor's
storefront page plus a '#product-<id>' fragment.

Page family: API. This spider reads a JSON API and never fetches a
browsable page; the collected item `url` values are synthetic anchors on
the vendor's SPA route (https://www.allmartplace.com/en/vendor/
TML-Mini-Mart#product-<id>), not real fetchable permalinks — the SPA
route itself renders client-side and returns no server-rendered product
markup, so there is nothing here for a Common-Crawl archive regex to
anchor on.
"""

import logging
from datetime import datetime, timezone
from urllib.parse import urlencode

import scrapy

logger = logging.getLogger(__name__)

API_BASE = "https://www.allmartplace.com/api"
VENDOR_PAGE_URL = "https://www.allmartplace.com/en/vendor/TML-Mini-Mart"

DOMAIN_NAME = "www.allmartplace.com"
MARKETPLACE_REFERENCE_ID = "efe8e3bdceee848c76c0b06fe6a2e22c"
MARKETPLACE_USER_ID = 227670
VENDOR_USER_ID = 1589747
PAGE_SIZE = 25


def _common_params() -> dict:
    return {
        "domain_name": DOMAIN_NAME,
        "post_to_get": 1,
        "marketplace_reference_id": MARKETPLACE_REFERENCE_ID,
        "marketplace_user_id": MARKETPLACE_USER_ID,
        "user_id": VENDOR_USER_ID,
        "dual_user_key": 0,
        "language": "en",
    }


class TmlminimartAgSpider(scrapy.Spider):
    name = "tmlminimart_ag"
    allowed_domains = ["allmartplace.com"]
    currency = "XCD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [429, 500, 502, 503, 504, 522, 524, 408],
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        params = _common_params()
        url = f"{API_BASE}/get_app_catalogue?{urlencode(params)}"
        yield scrapy.Request(
            url, callback=self.parse_top_categories, errback=self.errback
        )

    def parse_top_categories(self, response):
        payload = self._json(response)
        if payload is None:
            return
        data = payload.get("data") or []
        # get_app_catalogue wraps the category list one level deeper than
        # catalogue/get does: data == [[cat, cat, ...]].
        categories = data[0] if data and isinstance(data[0], list) else data
        yield from self._walk(categories)

    def parse_children(self, response):
        payload = self._json(response)
        if payload is None:
            return
        data = payload.get("data") or {}
        categories = data.get("result") or []
        yield from self._walk(categories)

    def _walk(self, categories):
        for cat in categories:
            cat_id = cat.get("catalogue_id")
            name = (cat.get("name") or "").strip()
            if not cat_id:
                continue
            if cat.get("has_children"):
                params = _common_params()
                params["parent_category_id"] = cat_id
                url = f"{API_BASE}/catalogue/get?{urlencode(params)}"
                yield scrapy.Request(
                    url,
                    callback=self.parse_children,
                    errback=self.errback,
                    dont_filter=True,
                )
            if cat.get("has_products"):
                yield self._product_page_request(cat_id, name, offset=0)

    def _product_page_request(self, cat_id, category, offset):
        params = _common_params()
        params["parent_category_id"] = cat_id
        params["offset"] = offset
        params["limit"] = PAGE_SIZE
        params["page_no"] = offset // PAGE_SIZE + 1
        params["date_time"] = datetime.now(timezone.utc).isoformat()
        url = f"{API_BASE}/get_products_for_category?{urlencode(params)}"
        return scrapy.Request(
            url,
            callback=self.parse_products,
            errback=self.errback,
            meta={"category": category, "catalogue_id": cat_id, "offset": offset},
            dont_filter=True,
        )

    def parse_products(self, response):
        payload = self._json(response)
        if payload is None:
            return
        products = payload.get("data") or []
        category = response.meta["category"]
        cat_id = response.meta["catalogue_id"]
        offset = response.meta["offset"]

        n = 0
        for p in products:
            item = self._item(p, category)
            if item:
                n += 1
                yield item
        logger.info(
            f"{self.name}: category={category!r} offset={offset} "
            f"products={len(products)} yielded={n}"
        )

        if len(products) == PAGE_SIZE:
            yield self._product_page_request(cat_id, category, offset + PAGE_SIZE)

    def _item(self, p: dict, category: str | None):
        price = p.get("price")
        if price is None:
            return None
        try:
            price = float(price)
        except (TypeError, ValueError):
            return None
        if price <= 0:
            return None
        product_id = str(p.get("product_id"))
        name = (p.get("name") or "").strip()
        if not name:
            return None
        return {
            "product_id": product_id,
            "product_name": name[:500],
            "category": category,
            "price": str(price),
            "currency": self.currency,
            "available": bool(p.get("is_enabled", 1)),
            "url": f"{VENDOR_PAGE_URL}#product-{product_id}",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def _json(self, response):
        try:
            return response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON response at {response.url}")
            return None

    def errback(self, failure):
        logger.warning(f"{self.name}: request failed: {failure.value!r}")
