"""
San Pedro Provisioning Company (Belize) -- https://sanpedroprovisioningcompany.com/.

Physical grocery-provisioning business based in San Pedro, Ambergris Caye,
Belize -- orders groceries and delivers locally (homes, vacation rentals)
within San Pedro. Not a US/diaspora ship-to-Caribbean retailer: the catalog
is described in first person as "our" local stock (Belize Chocolate
Company rum cream, "Belizean Baileys", homemade Belizean rum punch) and the
business exists to serve San Pedro residents and visitors.

Standard WooCommerce Store API (/wp-json/wc/store/v1/products), no auth.
currency_minor_unit=2. Verified live 2026-09-11: X-WP-Total 521 products
across 70+ categories spanning Produce (45), Meat and Seafood (31), Dairy
and Eggs (39), Bakery and Bread (24), Pantry (159), Beverages (63), Beer,
Spirits and Wine, Snacks -- a genuine full grocery catalog, not a curated
tourist hamper.

Currency: Store API's own currency_code field reports USD on every
product, not Belize's official BZD. Not overridden -- Belize's dollar is
pegged 2:1 to the US dollar and San Pedro's tourist-economy retailers
commonly quote and transact in USD directly; there is no BZD figure
anywhere in the payload to fall back to. Treated as a genuinely USD-priced
storefront, same reasoning as jollys_dm (Dominica) and caribeshop_nevis.

Enumerability confirmed live: per_page=20 page 1 vs page 2 -> 20/20 ids,
zero overlap. 19/20 sampled products carry a non-zero price.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class SanpedroprovisioningBzSpider(WooBaseSpider):
    name = "sanpedroprovisioning_bz"
    allowed_domains = ["sanpedroprovisioningcompany.com"]
    currency = "USD"
    language = "en"
    FORCE_CURRENCY = "USD"
    BASE_URL = "https://sanpedroprovisioningcompany.com/wp-json/wc/store/v1/products"
