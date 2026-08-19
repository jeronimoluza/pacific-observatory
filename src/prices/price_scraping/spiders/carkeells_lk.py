"""Spider for Carkeells (Sri Lanka) -- https://carkeells.lk/. OpenCart 4 SEO
theme; a small grocery/beverages tail (~55 SKUs) bolted onto an otherwise
cosmetics/health-dominant catalog, per prior research."""

from price_scraping.spiders._opencart_base import OpencartBaseSpider

CATEGORIES = ("food-products", "beverages")


class CarkeellsLkSpider(OpencartBaseSpider):
    name = "carkeells_lk"
    allowed_domains = ["carkeells.lk"]
    currency = "LKR"
    language = "en"
    CATEGORY_URLS = tuple(
        f"https://carkeells.lk/en-gb/catalog/grocery/{slug}" for slug in CATEGORIES
    )
