"""
Popas Poupança (Cabo Verde) — https://popaspoupancas.cv/.

Standard WooCommerce Store API. Wide wholesale grocery/beverage/hygiene
catalog (~823 products) with CVE prices at currency_minor_unit=2. Category
breakdown (measured 2026-08-31): Alimentos 235, Bebidas 183, PRODUTOS DE
ADEGA 477 (wine/cellar, overlaps Bebidas), Produtos de Higiene 145,
Produtos a Grossos 141, Doces e Snacks 76, Congelados 26, Master Fruits 16,
Laticinios 9 — food-and-beverage dominant. A handful of rows are the
business's own service fees ("Prestacao de servicos...", "Frete") rather
than retail SKUs; left in since they are a small minority and the pipeline
does not filter non-product rows for other WooCommerce sources either.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class PopasPoupancaCvSpider(WooBaseSpider):
    name = "popas_poupanca_cv"
    allowed_domains = ["popaspoupancas.cv"]
    currency = "CVE"
    language = "pt"
    BASE_URL = "https://popaspoupancas.cv/wp-json/wc/store/v1/products"
