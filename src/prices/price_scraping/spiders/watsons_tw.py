"""
Watsons Taiwan — https://www.watsons.com.tw/. Akamai bypassed via chrome120.

TW has no English sitemap variant (unlike SG/HK/TH/MY/PH/ID); product URLs only
appear in sitemap_prd_zh_TW_NN.xml, so this spider walks the Chinese sitemap and
records language='zh-TW'. Product names and breadcrumbs come back in Traditional
Chinese — COICOP classification at the downstream Gemini stage handles that.
"""

from price_scraping.spiders._watsons_base import WatsonsBaseSpider


class WatsonsTwSpider(WatsonsBaseSpider):
    name = "watsons_tw"
    allowed_domains = ["watsons.com.tw"]
    currency = "TWD"
    language = "zh-TW"

    SITEMAP_INDEX = "https://www.watsons.com.tw/sitemap.xml"
    SITEMAP_FILTER = "sitemap_prd_zh_TW"
    PRICE_SYMBOL = "NT$"
