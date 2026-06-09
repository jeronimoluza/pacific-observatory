"""Watsons Hong Kong — https://www.watsons.com.hk/. Akamai bypassed via chrome120."""

from price_scraping.spiders._watsons_base import WatsonsBaseSpider


class WatsonsHkSpider(WatsonsBaseSpider):
    name = "watsons_hk"
    allowed_domains = ["watsons.com.hk"]
    currency = "HKD"
    language = "en"

    SITEMAP_INDEX = "https://www.watsons.com.hk/sitemap.xml"
    SITEMAP_FILTER = "sitemap_prd_en"
    PRICE_SYMBOL = "HK$"
