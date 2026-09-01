"""CompuGhana (Ghana) -- https://compughana.com/. Electronics/computers/
appliances retailer. Standard Shopify storefront, /products.json open with
no auth. Prices confirmed GHS via on-page GH₵/GHS markup (2026-09-01)."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class CompughanaGhSpider(ShopifyBaseSpider):
    name = "compughana_gh"
    allowed_domains = ["compughana.com"]
    base_url = "https://compughana.com"
    currency = "GHS"
    language = "en"
