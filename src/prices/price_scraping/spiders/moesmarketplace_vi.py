"""
Spider for Moe's Marketplace (US Virgin Islands, St Thomas).

NCR Freshop tenant app_key=moes_marketplace, store_id=5430
("Moe's Marketplace - Margaritaville, Marinas, and Villas", St Thomas, USVI).
Probed live 2026-09-11: total=8866, unit_price populated (e.g. 'RIPE BANANA' $1.89).
Store selection matters on this tenant: ids 2721 and 2714 return LARGER totals
(14752 / 8944) but unit_price is null on every row -- they are catalog-only
parent stores. 5430 / 2825 / 2715 are the three priced storefronts and carry the
same prices; 5430 has the largest priced catalogue, so it is the one scraped.
Prices display as plain "$" and the territory is USD, matching countries.yaml.
Page family parsed: API (api.freshop.ncrcloud.com/2/products). Collected urls are
/shop/<dept>/<slug>/p/<id> storefront permalinks the spider never fetches.
"""

from price_scraping.spiders._freshop_base import FreshopBaseSpider


class MoesmarketplaceViSpider(FreshopBaseSpider):
    name = "moesmarketplace_vi"
    currency = "USD"
    language = "en"

    APP_KEY = "moes_marketplace"
    STORE_ID = "5430"
