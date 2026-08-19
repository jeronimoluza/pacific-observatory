"""Al-Fatah (Pakistan) -- https://alfatah.pk/. Karachi/Lahore department store
(household goods, homeware, general merchandise). Shopify catalog is open."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class AlfatahPkSpider(ShopifyBaseSpider):
    name = "alfatah_pk"
    allowed_domains = ["alfatah.pk"]
    base_url = "https://alfatah.pk"
    currency = "PKR"
    language = "en"
