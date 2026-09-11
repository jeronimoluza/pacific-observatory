"""
Samtronix Suriname -- https://samtronixsuriname.com/.

Standard WooCommerce Store API. Phones and electronics (e.g. 'REDMI
17C/8/256GB-BLACK') -- classified electronics.

Verified live 2026-09-11: x-wp-total=578, x-wp-totalpages=578 at
per_page=1 (i.e. 578 products, ~29 pages at per_page=20). Page 1 vs page
2 (per_page=20) returned disjoint product-id sets, zero overlap --
genuine pagination.

Currency: Store API reports currency_code=SRD -- matches Suriname's
country currency. currency_minor_unit=2 (e.g. price "663000" -> SRD
6,630.00), consistent with the post-devaluation SRD price level for a
mid-range smartphone.

Page family: API (Store API JSON; permalinks are real PDP URLs but never
fetched by this spider).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class SamtronixSrSpider(WooBaseSpider):
    name = "samtronix_sr"
    allowed_domains = ["samtronixsuriname.com", "www.samtronixsuriname.com"]
    currency = "SRD"
    language = "nl"
    BASE_URL = "https://samtronixsuriname.com/wp-json/wc/store/v1/products"
