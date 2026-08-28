"""Door To Door West (Trinidad and Tobago) — https://shop.doortodoortt.com/west/. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class DoorToDoorTtSpider(WooBaseSpider):
    name = "door_to_door_tt"
    allowed_domains = ["shop.doortodoortt.com"]
    currency = "TTD"
    language = "en"
    BASE_URL = "https://shop.doortodoortt.com/west/wp-json/wc/store/v1/products"
