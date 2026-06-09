"""Watsons Thailand — https://www.watsons.co.th/. Akamai bypassed via chrome120."""

from price_scraping.spiders._watsons_base import WatsonsBaseSpider


class WatsonsThSpider(WatsonsBaseSpider):
    name = "watsons_th"
    allowed_domains = ["watsons.co.th"]
    currency = "THB"
    language = "en"

    SITEMAP_INDEX = "https://www.watsons.co.th/sitemap.xml"
    SITEMAP_FILTER = "sitemap_prd_en"
    PRICE_SYMBOL = "฿"
