"""
Ourtelekom Shop (Solomon Islands) — https://shop.ourtelekom.com.sb/.

Discovery lead "telekom.com.sb" is a legacy/redirecting hostname for Our
Telekom (Solomon Telekom); the live site is ourtelekom.com.sb, whose
/shop/ path redirects to a distinct WooCommerce storefront on
shop.ourtelekom.com.sb (WordPress 7.1 / WooCommerce 9.9.7). This is a
DIFFERENT catalogue from the existing `our_telekom_plans` fetcher (which
scrapes the SSR tariff page for mobile/data PLANS): this spider covers the
device shop (phones/handsets), a small (41-SKU) but genuine retail catalogue
with SBD prices via the standard, unauthenticated Store API.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class OurtelekomShopSbSpider(WooBaseSpider):
    name = "ourtelekom_shop_sb"
    allowed_domains = ["shop.ourtelekom.com.sb"]
    currency = "SBD"
    language = "en"
    BASE_URL = "https://shop.ourtelekom.com.sb/wp-json/wc/store/v1/products"
