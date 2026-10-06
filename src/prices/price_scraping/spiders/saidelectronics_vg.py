"""
Said Electronics (British Virgin Islands) -- https://www.saidelectronics.com/.

Road Town electronics retailer (many variants list price 0.00 = quote only; base drops/keeps per its logic).
Shopify storefront, open /products.json catalog; Shopify.currency.active = USD.
"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class SaidelectronicsVgSpider(ShopifyBaseSpider):
    name = "saidelectronics_vg"
    allowed_domains = ["www.saidelectronics.com"]
    base_url = "https://www.saidelectronics.com"
    currency = "USD"
    language = "en"
