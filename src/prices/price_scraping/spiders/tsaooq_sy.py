"""
Tsaooq (Syria) — https://tsaooq.com/.

General Syrian marketplace (Facebook-catalog-style listings); only category
id 19 ("الأغذية والمشروبات" / Food & Beverages, count=4) is food, so we scope
to that category rather than walking the whole non-food catalog.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class TsaooqSySpider(WooBaseSpider):
    name = "tsaooq_sy"
    allowed_domains = ["tsaooq.com"]
    currency = "SYP"
    language = "ar"
    BASE_URL = "https://tsaooq.com/wp-json/wc/store/v1/products"
    CATEGORY_ID = 19
