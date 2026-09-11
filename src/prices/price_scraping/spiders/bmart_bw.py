"""Bmart -- Botswana Online Shopping -- https://bmart.co.bw/.

Standard WooCommerce Store API. Probed 2026-09-11: 79 products total
(one page at per_page=100), general-merchandise catalog -- printer
toners/parts, books & stationery (many Bibles, incl. Setswana-language
titles), baby toys, beauty & personal care. currency_code=BWP from the
API, minor_unit=2, matches countries.yaml. Pagination verified distinct
at per_page=5: page1 ids {9375,9378,9381,9384,9399} vs page2 ids
{9360,9363,9365,9369,9372}, zero overlap.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class BmartBwSpider(WooBaseSpider):
    name = "bmart_bw"
    allowed_domains = ["bmart.co.bw"]
    currency = "BWP"
    language = "en"
    BASE_URL = "https://bmart.co.bw/wp-json/wc/store/v1/products"
