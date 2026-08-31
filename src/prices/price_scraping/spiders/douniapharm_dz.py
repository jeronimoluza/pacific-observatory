"""
Douniapharm (Algeria) — https://douniapharm.com/.

Online parapharmacy (skincare, beauty, supplements, baby care). Standard
WooCommerce Store API. Re-verified live 2026-08-31: GET
/wp-json/wc/store/v1/products?per_page=10 -> 200 JSON, currency_code DZD,
currency_minor_unit=0 (whole-dinar prices, no division). X-WP-Total
reports 1,190 products / 119 pages. Zero-price placeholder rate is 0/200
sampled.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class DouniapharmDzSpider(WooBaseSpider):
    name = "douniapharm_dz"
    allowed_domains = ["douniapharm.com"]
    currency = "DZD"
    language = "fr"
    BASE_URL = "https://douniapharm.com/wp-json/wc/store/v1/products"
