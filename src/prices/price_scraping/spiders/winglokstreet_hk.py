"""Spider for Wing Lok Street (永樂街海味), a Hong Kong dried-seafood
and tonic-food specialty storefront (abalone, dried conch/sea snail, dried
scallop, fish maw)."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class WinglokstreetHkSpider(ShopifyBaseSpider):
    name = "winglokstreet_hk"
    allowed_domains = ["www.winglokstreet.com.hk"]
    base_url = "https://www.winglokstreet.com.hk"
    currency = "HKD"
    language = "zh"
