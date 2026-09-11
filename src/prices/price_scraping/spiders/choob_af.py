"""Choob.af (Afghanistan) — "Afghanistan's Largest E-Commerce Furniture
Company". WooCommerce Store API, plain HTTP (no impersonation needed —
`server: hcdn` (Huawei Cloud CDN) 403s curl_cffi TLS impersonation but
clears at 200 with a plain, non-impersonating request; the WooBaseSpider
default downloader path already does this). 196 products, currency_code
USD (site prices furniture in USD, common for large-ticket AFN-volatile
purchases in Afghanistan) — narrow furniture catalog, COICOP 05.1.1.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class ChoobAfSpider(WooBaseSpider):
    name = "choob_af"
    allowed_domains = ["choob.af"]
    currency = "USD"
    language = "en"
    BASE_URL = "https://choob.af/wp-json/wc/store/v1/products"
