"""Watsons Singapore — https://www.watsons.com.sg/. Akamai bypassed via chrome120."""

from price_scraping.spiders._watsons_base import WatsonsBaseSpider


class WatsonsSgSpider(WatsonsBaseSpider):
    name = "watsons_sg"
    allowed_domains = ["watsons.com.sg"]
    currency = "SGD"
    language = "en"

    SITEMAP_INDEX = "https://www.watsons.com.sg/sitemap.xml"
    SITEMAP_FILTER = "sitemap_prd_en"
    PRICE_SYMBOL = "S$"
