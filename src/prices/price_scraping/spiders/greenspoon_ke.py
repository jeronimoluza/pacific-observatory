"""
Greenspoon (Kenya) — https://greenspoon.co.ke/.

Organic/artisan grocer. DATA QUALITY: some products' `description` field
carries leftover unrelated HTML fragments from their CMS — not used here
since we only read name/prices/categories/permalink.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class GreenspoonKeSpider(WooBaseSpider):
    name = "greenspoon_ke"
    allowed_domains = ["greenspoon.co.ke"]
    currency = "KES"
    language = "en"
    BASE_URL = "https://greenspoon.co.ke/wp-json/wc/store/v1/products"
