"""
Carrefour Algérie (https://www.carrefour.dz/) — real Carrefour-branded
hypermarket e-commerce site, PleskLin/PHP host behind Cloudflare. Standard
WooCommerce Store API. Verified live 2026-08-31: GET
/wp-json/wc/store/v1/products?per_page=50 -> 200 JSON, currency_code DZD
(matches countries.yaml), currency_minor_unit=2. X-WP-Total reports only
171 products total (small, actively-curated catalogue, not a partial
listing — confirmed by walking all 171 and finding 0 duplicates). Category
breakdown: Alimentaire (36), Épicerie sucrée (20), Épicerie salée (11),
Fromage et Charcuterie (4), Le marché frais (4), Boisson (1) = ~76/171
(~44%) food/beverage SKUs; remainder is electroménager, hi-tech, mode,
jardinage etc. Zero-price rate 0/171 sampled. Whole-catalog walk, no
category filter.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class CarrefourDzSpider(WooBaseSpider):
    name = "carrefour_dz"
    allowed_domains = ["carrefour.dz", "www.carrefour.dz"]
    currency = "DZD"
    language = "fr"
    BASE_URL = "https://www.carrefour.dz/wp-json/wc/store/v1/products"
