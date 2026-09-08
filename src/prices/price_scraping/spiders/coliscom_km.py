"""
Coliscom (Comoros) — https://www.coliscom.fr/, "livraison a domicile de
courses dans l'Ocean Indien" (home grocery delivery in the Indian Ocean).

Discovery lead re-probed 2026-09-06: Shopify storefront (shop handle
"tiboutik-re", theme id 41), standard unauthenticated /products.json
catalog. 250 products on page 1 alone (limit=250) -- general household/
grocery goods (cookware, diapers, ... sampled).

LOCALITY-TRAP CHECK (per prior-wave guidance -- diaspora Shopify stores
serving a foreign country from elsewhere): `Shopify.country` on the
homepage is "RE" (La Reunion), not "KM" -- but the storefront's own
market/localization selector explicitly lists "Comores" (data-value="KM")
as a live market with its own currency block (EUR), alongside La Reunion
and Mayotte. This is a genuine multi-market Indian-Ocean grocery-delivery
operator, not a US-entity diaspora store that merely mentions Comoros --
confirmed by explicit market-selector markup, not inferred from copy.

CURRENCY GOTCHA ("declared wins"): countries.yaml defaults Comoros to
KMF, but the site prices and bills in EUR for every listed market
including the Comores (KM) one -- confirmed from the localization
selector's currency line ("EUR", "€") next to the Comores option.
Declared currency wins over the assumed local one (same precedent as
tongamarket/NZD, niront/USD).

Page family: API (spider reads products.json, never fetches a
www.coliscom.fr HTML page in either direction).
"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class ColiscomKmSpider(ShopifyBaseSpider):
    name = "coliscom_km"
    allowed_domains = ["coliscom.fr"]
    base_url = "https://www.coliscom.fr"
    currency = "EUR"
    language = "fr"
