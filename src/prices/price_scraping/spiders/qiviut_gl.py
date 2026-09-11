"""
Qiviut -- https://www.qiviut.gl/.

Musk-ox-wool knitwear and sealskin accessories, Greenland. Product names
are mixed English/Danish ("Hair clip with bow in musk ox wool" /
"Hårspænde med sløjfe i moskusuld") but the site's own <html lang="en-GB">
-- treated as English. Standard WooCommerce Store API, DKK prices at
currency_minor_unit=2, confirmed live 2026-09-11.

Enumerability confirmed: x-wp-total=211 across 15 pages (per_page=15).
page1 ids distinct from page2 ids -- catalog paginates cleanly.

No catalog overlap with the country's other onboarded source
(pisiffik_gl, a department-store/electronics/furniture franchise
operator) -- different company, different product category (musk-ox
wool/sealskin craft goods).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class QiviutGlSpider(WooBaseSpider):
    name = "qiviut_gl"
    allowed_domains = ["qiviut.gl"]
    currency = "DKK"
    language = "en"
    BASE_URL = "https://www.qiviut.gl/wp-json/wc/store/v1/products"
