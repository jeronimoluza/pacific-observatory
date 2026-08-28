"""El-Yahweh Online Grocery (Uganda, Kampala, WooCommerce) — https://elyahwehventures.com/"""

from price_scraping.spiders._woo_base import WooBaseSpider


class ElyahwehventuresUgSpider(WooBaseSpider):
    name = "elyahwehventures_ug"
    allowed_domains = ["elyahwehventures.com"]
    currency = "UGX"
    language = "en"
    BASE_URL = "https://elyahwehventures.com/wp-json/wc/store/v1/products"
