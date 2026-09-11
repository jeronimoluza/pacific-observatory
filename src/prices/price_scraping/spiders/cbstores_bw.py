"""CB Stores -- https://cbstores.co.bw/.

Shopify products.json catalog. Probed 2026-09-11: ~2,347 products
(2,250 across 9 full pages of 250 + 97 on page 10), clothing/footwear
retailer (kids/adult sandals, shirts, etc). /products.json itself carries
no currency field -- confirmed BWP from a live PDP's inline JSON
(`"currency":"BWP"`), JSON-LD `priceCurrency`, and the Shopify analytics
meta blob, all agreeing, despite this being a cross-border-adjacent
Southern African storefront where ZAR would have been the reasonable
default guess. Pagination verified distinct: page1 5 ids vs page2 5 ids,
zero overlap.
"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class CbstoresBwSpider(ShopifyBaseSpider):
    name = "cbstores_bw"
    allowed_domains = ["cbstores.co.bw"]
    base_url = "https://cbstores.co.bw"
    currency = "BWP"
    language = "en"
