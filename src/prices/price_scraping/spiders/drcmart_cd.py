"""DRC Mart (DR Congo, Shopify) — https://www.drcmart.com/

Electronics and mobile phone retailer. Shopify storefront config confirms
locality: Shopify.country = "CD", homepage title "Online Electronics &
Mobile Phones Store in Kinshasa, DRC". Dollarised (Shopify.currency active
USD), which matches how DRC's big-ticket electronics retail is actually
priced.
"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class DrcmartCdSpider(ShopifyBaseSpider):
    name = "drcmart_cd"
    allowed_domains = ["drcmart.com"]
    base_url = "https://www.drcmart.com"
    currency = "USD"
    language = "en"
