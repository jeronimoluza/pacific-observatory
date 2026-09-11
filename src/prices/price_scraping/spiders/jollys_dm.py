"""
Jollys Pharmacy (Dominica) -- https://jollys.dm/.

Standard WooCommerce Store API. currency_minor_unit=2.

Currency: the Store API's own currency_code field reports "USD", not
Dominica's official XCD -- verified live rather than trusted blind. The PDP
(e.g. /product/crude-coconut-oil-1-gallon/) renders the WooCommerce price
with a bare "$" symbol and no "XCD"/"EC$" string anywhere on the page; the
site runs the "WooCommerce Product Price Based on Countries" plugin
(wp-content/plugins/woocommerce-product-price-based-on-countries), which
geolocates the visitor via an AJAX call after page load and can swap the
displayed currency per country, but the pre-AJAX server-rendered default
-- what both curl_cffi and the Store API return -- is USD with no XCD
anywhere in the shipped HTML/JSON. Treated as a genuine USD-priced
storefront (common for Caribbean pharmacies transacting near the XCD peg),
per FORCE_CURRENCY below rather than trusting countries.yaml's XCD default.

Enumerability confirmed: per_page=50 page 1 vs page 2 -> 50/50 rows, 0 id
overlap. Catalog is large -- walked 60 pages x100 without emptying
(6,000+ SKUs), a big pharmacy/general-goods catalog.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class JollysDmSpider(WooBaseSpider):
    name = "jollys_dm"
    allowed_domains = ["jollys.dm"]
    currency = "USD"
    language = "en"
    FORCE_CURRENCY = "USD"
    BASE_URL = "https://jollys.dm/wp-json/wc/store/v1/products"
