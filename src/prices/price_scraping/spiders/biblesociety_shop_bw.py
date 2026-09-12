"""Bible Society of Botswana shop -- https://shop.biblesociety.org.bw/.

WooCommerce with the Store API firewalled (401 on /wp-json/wc/store/v1/
products), so this goes through the sitemap route. WordPress core sitemap
shard /wp-sitemap-posts-product-1.xml lists 36 /product/ PDPs, each with a
WooCommerce JSON-LD Product node. Verified: "Tswana Bible 1908" BWP 200.00
and a brown variant at BWP 220.00.

Setswana-language scripture and religious books -- COICOP 09.7 / 12.x
territory that nothing else in the Botswana set reaches.

Page family: PDP only -- sitemap-driven.
"""

from __future__ import annotations

from ._woo_sitemap_base import WooSitemapBaseSpider


class BiblesocietyShopBwSpider(WooSitemapBaseSpider):
    name = "biblesociety_shop_bw"
    allowed_domains = ["shop.biblesociety.org.bw"]
    SITEMAP_URL = "https://shop.biblesociety.org.bw/wp-sitemap-posts-product-1.xml"
    PRODUCT_URL_RE = r"/product/"
    currency = "BWP"
    language = "en"
