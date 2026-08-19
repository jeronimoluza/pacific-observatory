"""Spider for Ogi Market (Bulgaria) -- https://ogimarket.bg/. Fully
SEO-rewritten clean URLs (no route=/path= params), so categories are listed
explicitly rather than auto-discovered."""

from price_scraping.spiders._opencart_base import OpencartBaseSpider

CATEGORIES = (
    "bio-specialni-hrani",
    "domashni-lubimci",
    "gotveno",
    "hlebni-i-testeni",
    "kolbasi-i-delikatesi",
    "meso-i-riba",
    "mlechni-i-yaica",
    "napitki",
    "paketirani-hrani",
    "plodove-i-zelenchuci",
    "plodovi-mleka-i-deserti",
    "za-bebeto-i-deteto",
    "za-doma-i-ofisa",
    "zamrazeni-hrani",
)


class OgimarketBgSpider(OpencartBaseSpider):
    name = "ogimarket_bg"
    allowed_domains = ["ogimarket.bg"]
    currency = "EUR"
    language = "bg"
    LIMIT = 100
    CATEGORY_URLS = tuple(f"https://ogimarket.bg/{slug}" for slug in CATEGORIES)
