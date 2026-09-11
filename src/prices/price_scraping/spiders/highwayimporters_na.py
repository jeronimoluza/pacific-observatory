"""
Highway Importers -- https://highwayimporters.com.na/ (general-merchandise
importer/dropshipper: beauty, gadgets, kitchenware, home & garden, toys,
office supplies, Namibia).

Standard WooCommerce Store API at /wp-json/wc/store/v1/products. NAD
prices at currency_minor_unit=2, confirmed against the site's own
price_html on the same row.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class HighwayimportersNaSpider(WooBaseSpider):
    name = "highwayimporters_na"
    allowed_domains = ["highwayimporters.com.na"]
    currency = "NAD"
    language = "en"
    BASE_URL = "https://highwayimporters.com.na/wp-json/wc/store/v1/products"
