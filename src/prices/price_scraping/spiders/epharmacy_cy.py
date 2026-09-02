"""
ePharmaCY (Cyprus) — https://epharmacy.net/.

Standard Shopify storefront (shop domain epharmacy-cy.myshopify.com), public
/products.json catalog, ~1,205 products across pharmacy/wellness/beauty
brands (GUAM, Marvis, Caudalie, etc). Shop currency confirmed EUR /
country CY via the inline `Shopify.currency = {"active":"EUR",...}` /
`Shopify.country = "CY"` blob on the homepage.
"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class EpharmacyCySpider(ShopifyBaseSpider):
    name = "epharmacy_cy"
    allowed_domains = ["epharmacy.net"]
    base_url = "https://epharmacy.net"
    currency = "EUR"
    language = "en"
