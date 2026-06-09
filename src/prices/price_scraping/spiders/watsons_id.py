"""Watsons Indonesia — https://www.watsons.co.id/. Akamai bypassed via chrome120."""

from price_scraping.spiders._watsons_base import WatsonsBaseSpider


class WatsonsIdSpider(WatsonsBaseSpider):
    name = "watsons_id"
    allowed_domains = ["watsons.co.id"]
    currency = "IDR"
    language = "en"

    SITEMAP_INDEX = "https://www.watsons.co.id/sitemap.xml"
    SITEMAP_FILTER = "sitemap_prd_en"
    PRICE_SYMBOL = "Rp"
