"""Cool Planet Online — Sri Lanka fashion retailer (Shopify) — https://coolplanet.lk/"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class CoolPlanetLkSpider(ShopifyBaseSpider):
    name = "coolplanet_lk"
    allowed_domains = ["coolplanet.lk"]
    base_url = "https://coolplanet.lk"
    currency = "LKR"
    language = "en"
