"""ShopOnline Bhutan (Shopify) — https://shoponline.bt/"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class ShoponlineBtSpider(ShopifyBaseSpider):
    name = "shoponline_bt"
    allowed_domains = ["shoponline.bt"]
    base_url = "https://shoponline.bt"
    currency = "BTN"
    language = "en"
