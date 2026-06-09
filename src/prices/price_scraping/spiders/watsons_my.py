"""Watsons Malaysia — https://www.watsons.com.my/. Akamai bypassed via chrome120."""

from price_scraping.spiders._watsons_base import WatsonsBaseSpider


class WatsonsMySpider(WatsonsBaseSpider):
    name = "watsons_my"
    allowed_domains = ["watsons.com.my"]
    currency = "MYR"
    language = "en"

    SITEMAP_INDEX = "https://www.watsons.com.my/sitemap.xml"
    SITEMAP_FILTER = "sitemap_prd_en"
    PRICE_SYMBOL = "RM"
