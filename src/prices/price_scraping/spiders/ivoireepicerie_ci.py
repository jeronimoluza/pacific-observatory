"""
Ivoire Epicerie (Cote d'Ivoire) -- https://ivoireepicerie.com/.

Standard Shopify storefront. Open, unauthenticated catalog at
/products.json?limit=250&page=N (page 2 empty -- 21 SKUs total, entirely
food: spice/powder blends, moringa, garlic powder, etc., vendor tag
"Ivoire epicerie" on every product). Storefront reports currency XOF
(Shopify.currency.active = "XOF"), matching countries.yaml.
"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class IvoireepicerieCiSpider(ShopifyBaseSpider):
    name = "ivoireepicerie_ci"
    allowed_domains = ["ivoireepicerie.com"]
    base_url = "https://ivoireepicerie.com"
    currency = "XOF"
    language = "fr"
