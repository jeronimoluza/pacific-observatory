"""
Alawao (Cuba diaspora grocery/pharmacy/general-merchandise delivery site)
-- https://alawao.com/.

Same shape as the other Cuba sources: pay abroad (USD), deliver to Cuba.
This is a real, usable Cuba price signal but it is NOT a domestic Cuban
retail price in CUP -- do not treat rows from this source as domestic CUP
retail.

Standard WooCommerce storefront; the versioned Store API is open with no
anti-bot gate (verified live 2026-09-01: plain `requests` with a browser UA,
no curl_cffi impersonation needed, returns 200). X-WP-Total: 2267 across
454 pages of 5; paginates cleanly (page 1 vs page 2 product ids fully
disjoint). Sample: "Postal de Felicitacion" USD 0 (free-with-purchase
insert card -- real catalog includes priced groceries, farmacia/OTC
medication lines, cantinas (prepared meals), and mayoristas (wholesale
packs)).

Catalog spans groceries (pasillo/servicio-mercado), pharmacy/OTC
(pasillo/servicio-farmacia -- antibioticos, analgesicos, antihistaminicos,
etc.), prepared-food cantinas, and general merchandise -> channel is
marketplace rather than supermarket or pharmacy, matching the breadth
precedent of mallhabana_cu / tuambia_cu.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class AlawaoCuSpider(WooBaseSpider):
    name = "alawao_cu"
    allowed_domains = ["alawao.com"]
    currency = "USD"
    language = "es"
    BASE_URL = "https://alawao.com/wp-json/wc/store/v1/products"
