"""Add2Cart Malawi (Shopify) — https://www.add2cartmw.com/"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class Add2cartmwSpider(ShopifyBaseSpider):
    name = "add2cartmw"
    allowed_domains = ["add2cartmw.com"]
    base_url = "https://www.add2cartmw.com"
    currency = "MWK"
    language = "en"
