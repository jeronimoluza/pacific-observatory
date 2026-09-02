"""
Supérette DZ (https://superette-dz.com/) — dedicated Algerian online grocer
(fr/ar storefronts under /fr/ and /ar/, same catalogue). Standard
WooCommerce Store API. Verified live 2026-08-31: GET
/wp-json/wc/store/v1/products?per_page=50 -> 200 JSON, currency_code DZD
(matches countries.yaml), currency_minor_unit=0 (whole-dinar prices, no
division). X-WP-Total reports 1,458 products / 30 pages. Overwhelmingly
food/beverage: top categories are Epicerie (349), Conserves et
Conditionnés (142), Produits laitiers (137), Epices et herbes (134),
Boissons (120), Petit déjeuner (119), Tomates et sauces (78), Fromages
(76), Légumes et fruits secs (74), Pâtisserie (71), Boissons gazeuses
(58), Biscuiterie et snacks (48), Chocolats et confiseries (44), Jus (43),
Cafés (32) — vs. a smaller non-food tail (Détergents 262, Produits
nettoyants 95, Cosmétique 50, Couches et lingettes 42). Zero-price rate
0/100 sampled. Whole-catalog walk, no category filter.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class SuperetteDzSpider(WooBaseSpider):
    name = "superette_dz"
    allowed_domains = ["superette-dz.com"]
    currency = "DZD"
    language = "fr"
    BASE_URL = "https://superette-dz.com/wp-json/wc/store/v1/products"
