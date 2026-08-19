"""
Spider for Nha Kretxeu (Cabo Verde) — https://www.nhakretxeu.com/supermercado.html.

Magento (Luma theme) SSR HTML; /rest/V1/products 401s (auth required), so
this reads the server-rendered supermercado.html category listing directly.
Standard Magento ?p=N pagination advances the grid (verified: page 2 returns
different product ids than page 1).
"""

from price_scraping.spiders._magento_base import MagentoSSRBaseSpider


class NhaKretxeuSpider(MagentoSSRBaseSpider):
    name = "nha_kretxeu"
    allowed_domains = ["nhakretxeu.com"]
    currency = "CVE"
    language = "pt"

    START_URLS = ["https://www.nhakretxeu.com/supermercado.html"]
    PAGE_PARAM = "p"
