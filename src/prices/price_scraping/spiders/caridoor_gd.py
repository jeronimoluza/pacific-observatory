"""
Caridoor ("The Caribbean at Your Door") — https://www.caridoor.com/.

Standard WooCommerce Store API. Small grocery catalog (~249 products) sold
in USD, one shared catalog serving multiple Eastern Caribbean islands
including Grenada (no per-country storefront split). Cloudflare fronts the
domain with a JS-challenge page under a plain (non-impersonated) client,
but the repo's pinned curl_cffi profile clears it with a plain 200 --
confirmed via manual curl_cffi probe before writing this spider.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class CaridoorGdSpider(WooBaseSpider):
    name = "caridoor_gd"
    allowed_domains = ["caridoor.com"]
    currency = "USD"
    language = "en"
    BASE_URL = "https://www.caridoor.com/wp-json/wc/store/v1/products"
