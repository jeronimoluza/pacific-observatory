"""
Mes Courses BJ (Benin) -- https://mescoursesbj.com/.

Standard Shopify storefront. Open, unauthenticated catalog at
/products.json?limit=250&page=N. 139 SKUs across 3 pages, genuine grocery
catalog (Riz GINO 25kg, Pringles, frozen peas, Poudre de Moringa, ...).
Site copy repeatedly names Cotonou/Benin as the service area.

CURRENCY GOTCHA: Shopify.currency.active = "EUR" -- prices are
EUR-denominated (e.g. rice 25kg at ~66 EUR), NOT XOF (countries.yaml
default). Per the "flag diaspora/foreign-currency pricing" rule: this
reads as a diaspora- or import-facing storefront pricing in EUR rather
than a domestic Beninese price level. Shipped anyway (real catalog, real
prices) but flagged here and in the manifest notes so downstream PPP
analysis does not treat it as a local price level without adjustment.
"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class MescoursesbjBjSpider(ShopifyBaseSpider):
    name = "mescoursesbj_bj"
    allowed_domains = ["mescoursesbj.com"]
    base_url = "https://mescoursesbj.com"
    currency = "EUR"
    language = "fr"
