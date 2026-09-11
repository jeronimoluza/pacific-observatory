"""
Meqqusaalik -- https://www.meqqusaalik.gl/.

Greenlandic clothing brand (anoraks/annoraat, trousers/qarliit, t-shirts),
sold in Kalaallisut (site's own <html lang="kl-gl">). Standard WooCommerce
Store API, DKK prices at currency_minor_unit=2, confirmed live 2026-09-11.

Enumerability confirmed: x-wp-total=73 across 5 pages (per_page=15).
page1 ids distinct from page2 ids -- catalog paginates cleanly.

No catalog overlap with the country's other onboarded source
(pisiffik_gl, a department-store/electronics/furniture franchise
operator) -- different company, different product category (apparel).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class MeqqusaalikGlSpider(WooBaseSpider):
    name = "meqqusaalik_gl"
    allowed_domains = ["meqqusaalik.gl"]
    currency = "DKK"
    language = "kl"
    BASE_URL = "https://www.meqqusaalik.gl/wp-json/wc/store/v1/products"
