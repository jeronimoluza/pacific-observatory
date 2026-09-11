"""Spider for Waafiro (Gambia) -- https://waafiro.com/.

Broad multi-vendor marketplace (fashion/phones/electronics/appliances/
furniture/eyewear/food/cosmetics/services). Per the COICOP 01/02-only
mandate for this onboarding pass, this spider is SCOPED to the site's
food-and-drink categories only -- it does not crawl the non-food catalog.

Fingerprinted 2026-09-11: React SPA, no server-rendered product data in raw
HTML. Playwright network-capture on the homepage found a plain JSON API,
no auth: GET https://waafiro.com/api/categories (250 categories, flat list
with id/name/description/parentId) and
GET https://waafiro.com/api/products?categoryId=<id>&limit=<n>&page=<n>.

Verified live 2026-09-11: filtering the 250 categories to food/drink names
(groceries, produce, dairy, rice/grains, fish/meat/poultry, cooking oil/
spices, beverages, snacks, canned goods, ...) and excluding restaurant/
prepared-food services (Fast Food, Grills & BBQ, Catering -- COICOP 11, not
01/02) leaves 29 categories; summed product count across them = 68 SKUs
(Local Drinks & Juice 16, Agriculture & Livestock 13, Fresh Juices 11,
Groceries 11, Fresh Produce 5, Other Groceries 5, Bottled & Packaged Drinks
3, Fish/Meat/Poultry 2, African Cuisine 1, Rice/Grains/Flour 1). Passes the
>=5-row gate comfortably. PDP permalink pattern confirmed live (200):
/product/<uuid> (SPA shell, but a stable canonical URL per product id).

Currency: no explicit currency field in the API payload; GMD is the only
currency in use on this Gambia-only storefront (matches countries.yaml).
Channel is marketplace (seller-authored listings, not a single retailer).
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_API_PRODUCTS = "https://waafiro.com/api/products"
_PAGE_SIZE = 100

# Food & drink categories only (COICOP 01/02). Excludes restaurant / prepared
# food services (Fast Food & Burgers, Grills & BBQ, Catering & Cooking,
# Juice Bars & Smoothies, Smoothies & Blended Drinks, Agricultural Services,
# Pesticides & Fertilisers, Seeds & Seedlings, Restaurants/Food & Dining
# umbrella) which are either COICOP 11 (restaurants) or non-retail inputs.
_FOOD_CATEGORY_IDS = {
    "67d4620e-46ef-4c6f-9b3a-a71883bacc6a": "Groceries",
    "ab70fd03-8f27-41b5-93ae-22748ddd741e": "Other Groceries",
    "e31fb927-80b8-477b-b5bf-1654cff70538": "Fresh Produce",
    "5a0cebc2-c034-4e2c-a342-09df72fa0c44": "Vegetables & Fruits",
    "3e0d4e61-cdf3-4b2f-bba3-a56690724b44": "Dairy & Eggs",
    "7578a9ed-426f-4ba6-8569-e3f10dd0eec2": "Fish, Meat & Poultry",
    "1ece3ea1-b039-455b-a86b-b3cd86ca9597": "Rice, Grains & Flour",
    "ecc477b7-cf9a-4b34-b85c-3a2461d91cb7": "Cooking Oil & Spices",
    "7eaf2e46-4848-430b-9205-ecf59976470c": "Herbs & Spices",
    "90a59c06-5357-449a-9cce-94db96bf1477": "Dried & Preserved Foods",
    "aaacd7c3-3b24-4d2d-b900-579aaeaad239": "Packaged Foods",
    "b6f1c270-404f-45f0-9fc8-0ac37c753ac7": "Canned & Packaged Goods",
    "5e55d668-85ea-4205-b8ac-f6eb16f437a1": "Snacks & Sweets",
    "6ea2319d-2bd7-4deb-9e1f-608abe4acb53": "Snacks & Street Food",
    "9389c571-32fb-4357-bdee-73019d51047b": "Beverages",
    "119affd9-a990-4772-90bc-470cc266f29f": "Drinks & Beverages",
    "a502d82c-fd85-4a43-b6f4-b42c1df5fff6": "Bottled & Packaged Drinks",
    "2ffcb0bf-1d2c-4635-abb3-ce7577ed1a38": "Local Drinks & Juice",
    "b7f95ef2-9bec-450d-bfec-61aacc292f6b": "Other Local Drinks",
    "2d9a5689-4a58-498e-ac8f-5df13b299abb": "Fresh Juices",
    "6c9f95a7-264e-43e9-8694-47eb1ee5a10f": "African Cuisine",
    "5584e3e1-dfd5-4b32-b869-6c9f0d8b5adf": "International Cuisine",
    "0f3008d9-5d42-43a0-8695-ef78af0d3bab": "Other Food & Dining",
    "7d3c20a1-dd06-4a46-8d7a-b855410ba0f4": "Agriculture & Livestock",
    "af3b10a3-4ab3-42b7-a225-9feacad73512": "Other Agriculture",
    "bc55042e-ca78-46d8-a6d9-bf13bf2c97ef": "Baby & Infant Products",
    "fff5d574-f63f-44d9-a67d-99bfb68ecfc7": "Baby Food & Formula",
    "169f97ea-96c4-4dd4-a971-0076db8f7ee3": "Bread & Bakery",
}


class WaafiroGmSpider(scrapy.Spider):
    name = "waafiro_gm"
    allowed_domains = ["waafiro.com"]
    currency = "GMD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
    }

    def start_requests(self):
        for cat_id, cat_name in _FOOD_CATEGORY_IDS.items():
            yield scrapy.Request(
                f"{_API_PRODUCTS}?categoryId={cat_id}&limit={_PAGE_SIZE}&page=1",
                callback=self.parse,
                headers={
                    "Referer": "https://waafiro.com/",
                    "Accept": "application/json",
                },
                meta={"cat_id": cat_id, "cat_name": cat_name, "page": 1},
            )

    def parse(self, response):
        try:
            products = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON response at {response.url}")
            return
        if not isinstance(products, list):
            products = products.get("data") or products.get("items") or []
        cat_name = response.meta["cat_name"]
        page = response.meta["page"]
        logger.info(f"{self.name}: cat={cat_name} page={page} got={len(products)}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in products:
            price = p.get("price")
            if price is None:
                continue
            pid = p.get("id")
            if not pid:
                continue
            yield {
                "product_id": str(pid),
                "product_name": str(p.get("name") or "").strip()[:500],
                "category": cat_name,
                "price": str(price),
                "currency": self.currency,
                "available": p.get("status") == "active",
                "url": f"https://waafiro.com/product/{pid}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        if len(products) == _PAGE_SIZE:
            next_page = page + 1
            cat_id = response.meta["cat_id"]
            yield scrapy.Request(
                f"{_API_PRODUCTS}?categoryId={cat_id}&limit={_PAGE_SIZE}&page={next_page}",
                callback=self.parse,
                headers={
                    "Referer": "https://waafiro.com/",
                    "Accept": "application/json",
                },
                meta={"cat_id": cat_id, "cat_name": cat_name, "page": next_page},
            )
