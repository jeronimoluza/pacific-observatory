"""Shop En Ligne Gabon (Gabon, Libreville, WooCommerce) — https://shopenlignegabon.net/"""

from price_scraping.spiders._woo_base import WooBaseSpider


class ShopenlignegabonGaSpider(WooBaseSpider):
    name = "shopenlignegabon_ga"
    allowed_domains = ["shopenlignegabon.net"]
    currency = "XAF"
    language = "fr"
    BASE_URL = "https://shopenlignegabon.net/wp-json/wc/store/v1/products"
