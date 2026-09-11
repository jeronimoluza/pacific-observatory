"""Keto Thai (Saipan, Northern Mariana Islands) — https://ketothaisaipan.com. WooCommerce Store API.

WooCommerce Store API v1, unauthenticated. 58 products, 49 priced (probed 2026-09-11).
prices.currency_code=USD, currency_minor_unit=2 (matches countries.yaml).
Single Saipan restaurant's online menu -- dishes, pizza, soup, rice, beverages. Almost all
rows are COICOP 11.1.1 (restaurant meals); left on the classifier per the build rules
rather than pinned with source_curated.
Nine rows carry price 0 (menu items with no online price); the base spider drops those.
GOTCHA: curl_cffi impersonate=chrome124 gets a 6,192-byte 403 from this host while a plain
requests call with a browser UA returns 200 -- a JA3 denylist, not a WAF. The Scrapy
default handler is fine.
Page family parsed: API (/wp-json/wc/store/v1/products).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class KetothaisaipanMpSpider(WooBaseSpider):
    name = "ketothaisaipan_mp"
    allowed_domains = ["ketothaisaipan.com"]
    currency = "USD"
    language = "en"
    BASE_URL = "https://ketothaisaipan.com/wp-json/wc/store/v1/products"
