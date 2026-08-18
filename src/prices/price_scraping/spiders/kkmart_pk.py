"""KK Mart (Pakistan) -- https://kkmart.pk/. General convenience-store
webshop (bakery, cosmetics, baby, household). Shopify catalog is open."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class KkmartPkSpider(ShopifyBaseSpider):
    name = "kkmart_pk"
    allowed_domains = ["kkmart.pk"]
    base_url = "https://kkmart.pk"
    currency = "PKR"
    language = "en"
