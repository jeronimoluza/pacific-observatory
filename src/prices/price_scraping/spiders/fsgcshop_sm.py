"""Shop FSGC -- https://shop.fsgc.sm/ (San Marino Football Federation official shop).

WooCommerce Store API at the non-versioned route /wp-json/wc/store/products (the v1 route 404s
on this tenant), 6 products, EUR (probed 2026-10-12).
Page family: API.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class FsgcshopSmSpider(WooBaseSpider):
    name = "fsgcshop_sm"
    allowed_domains = ["shop.fsgc.sm"]
    currency = "EUR"
    language = "it"
    BASE_URL = "https://shop.fsgc.sm/wp-json/wc/store/products"
