"""Spider for Al Mustawda (big.ly) (Libya) -- https://big.ly/food. Fully
SEO-rewritten clean URLs (`/food/<Slug>` for both subcategories and
products, no numeric ids anywhere), so categories are listed explicitly.
Includes the subcategories the original probe flagged as unwalked
(chocolate/drinks/fruits/goods) alongside /food itself (fresh produce)."""

from price_scraping.spiders._opencart_base import OpencartBaseSpider

CATEGORIES = ("food", "food/chocolate", "food/drinks", "food/fruits", "food/goods")


class BiglyLySpider(OpencartBaseSpider):
    name = "bigly_ly"
    allowed_domains = ["big.ly"]
    currency = "LYD"
    language = "ar"
    CATEGORY_URLS = tuple(f"https://big.ly/{slug}" for slug in CATEGORIES)
