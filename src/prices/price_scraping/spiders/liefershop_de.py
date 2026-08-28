"""
Spider for Liefershop.de (Germany) — https://www.liefershop.de/.

WooCommerce Store API, confirmed live 2026-08-06:
GET /wp-json/wc/store/v1/products?per_page=100&page=N -> 200, structured
JSON, EUR minor-unit prices.

CAVEAT (round 1 confirmed, reproduced here): the catalogue is heavily
interleaved with Juice Plus+ MLM shake/supplement products (the first page
sampled is almost entirely 'Juice Plus+ Perform Shake', 'Juice Plus+
Complete Chocolate Shakes', etc.), but deeper pages carry genuine F&B SKUs
per round 1 — 'Lamotte & Cie Champagne Brut', 'Tavernello Vino Rosato
d'Italia', 'Cinema Popcorn süss', 'Nestlé Cerealien Mini Packs'. Left
unfiltered on purpose (per WooBaseSpider convention) — the downstream
COICOP classifier/veto layer is the right place to drop MLM rows, not the
spider.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class LiefershopDeSpider(WooBaseSpider):
    name = "liefershop_de"
    allowed_domains = ["liefershop.de"]
    currency = "EUR"
    language = "de"
    BASE_URL = "https://www.liefershop.de/wp-json/wc/store/v1/products"
