"""Al-Ikhsan Malaysia sports apparel and footwear Shopify feed."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class AlIkhsanMySpider(ShopifyBaseSpider):
    name = "al_ikhsan_my"
    allowed_domains = ["al-ikhsan.com", "www.al-ikhsan.com"]
    base_url = "https://www.al-ikhsan.com"
    currency = "MYR"
    language = "en"
