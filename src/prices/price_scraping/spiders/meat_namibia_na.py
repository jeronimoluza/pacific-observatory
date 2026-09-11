"""
Buschmann Meat Packers -- https://meat-namibia.com/ (Windhoek, Namibia
butcher / meat-box delivery).

WooCommerce, but a non-standard install: the Store API lives at
/wp-json/wc/store/products (no `/v1/` segment), confirmed by walking the
site's own /wp-json/ route index -- see _woo_base.py's docstring, which
already anticipates this variant. prices.currency_code = "NAD" explicit
(no guessing needed, unlike kws_na/doorstep_na). No currency_minor_unit
field in the payload; _woo_base defaults minor=0, and prices are already
plain decimals (e.g. "20" -> N$20.00), confirmed against price_range
(min_amount "20.00" == the flat "price" field for the cheapest variant).

Small catalog: X-WP-Total=5, X-WP-TotalPages=1 -- only 5 parent products
(each a variable product with weight-based variants; the Store API's
`price`/`price_range` exposes only the min/max across variants, not each
variant individually -- the wc/blocks variations endpoint 401s
unauthenticated). This is genuinely the whole catalog, not a truncated
page (5 < per_page=100, so the base class's own-page-size check confirms
it stopped for the right reason).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class MeatNamibiaNaSpider(WooBaseSpider):
    name = "meat_namibia_na"
    allowed_domains = ["meat-namibia.com"]
    currency = "NAD"
    language = "en"
    BASE_URL = "https://meat-namibia.com/wp-json/wc/store/products"
