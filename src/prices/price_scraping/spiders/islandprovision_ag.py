"""
Island Provision Group (Antigua and Barbuda) — https://islandprovision.com/.

Standard WooCommerce Store API on the versioned route. Grocery/food-service
catalog (meat, canned goods, baked goods, pantry, condiments, spices, rice,
pasta) with USD prices at currency_minor_unit=2. Multi-division site
covering Island Provision Food Distribution, Gourmet Basket Supermarket,
Best Cellars Wines & Spirits and Yacht Provisioning; physical address
"Island Provision Complex, Sir George H. Walter Highway" and +1268 phone
numbers confirmed via /contact-us/ -- a real Antigua warehouse/storefront,
not a diaspora dropship shop (USD pricing here reflects the yacht/tourism
provisioning trade, which is genuinely dollarized in Antigua).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class IslandprovisionAgSpider(WooBaseSpider):
    name = "islandprovision_ag"
    allowed_domains = ["islandprovision.com"]
    currency = "USD"
    language = "en"
    BASE_URL = "https://islandprovision.com/wp-json/wc/store/v1/products"
