"""Watsons Philippines — https://www.watsons.com.ph/. Akamai bypassed via chrome120."""

from price_scraping.spiders._watsons_base import WatsonsBaseSpider


class WatsonsPhSpider(WatsonsBaseSpider):
    name = "watsons_ph"
    allowed_domains = ["watsons.com.ph"]
    currency = "PHP"
    language = "en"

    SITEMAP_INDEX = "https://www.watsons.com.ph/sitemap.xml"
    SITEMAP_FILTER = "sitemap_prd_en"
    PRICE_SYMBOL = "₱"

    # PH sitemap is larger than HK/SG/ID; prior 4h cap (CLOSESPIDER_TIMEOUT=14400)
    # truncated at 11,622/closespider_timeout while spider was still healthy.
    custom_settings = {
        **WatsonsBaseSpider.custom_settings,
        "CLOSESPIDER_TIMEOUT": 28800,
    }
