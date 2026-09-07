"""Wilco Vanuatu OpenCart catalog."""

from price_scraping.spiders._opencart_base import OpencartBaseSpider


class WilcoVuSpider(OpencartBaseSpider):
    name = "wilco_vu"
    allowed_domains = ["wilco.com.vu", "www.wilco.com.vu"]
    currency = "VUV"
    language = "en"
    CATEGORY_URLS = (
        "https://www.wilco.com.vu/index.php?route=product/category&path=175&limit=100",
        "https://www.wilco.com.vu/index.php?route=product/category&path=270&limit=100",
    )
    LIMIT = 100
    MAX_PAGES = 1
