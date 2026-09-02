"""Spider for Al Mustawda (big.ly) (Libya) -- https://big.ly/food. Fully
SEO-rewritten clean URLs (`/food/<Slug>` for both subcategories and
products, no numeric ids anywhere), so categories are listed explicitly.
Includes the subcategories the original probe flagged as unwalked
(chocolate/drinks/fruits/goods) alongside /food itself (fresh produce)."""

from price_scraping.spiders._opencart_base import OpencartBaseSpider

CATEGORIES = ("food", "food/chocolate", "food/drinks", "food/fruits", "food/goods")


class BiglyLySpider(OpencartBaseSpider):
    # Parent category "food" re-lists every product already under its own
    # leaves; verified 2026-09-01 that all 348 repeated ids carry identical
    # name and price, so this drops 791 rows to 437 real products.
    DEDUPE_PRODUCT_IDS = True

    name = "bigly_ly"
    allowed_domains = ["big.ly"]
    currency = "LYD"
    language = "ar"
    CATEGORY_URLS = tuple(f"https://big.ly/{slug}" for slug in CATEGORIES)
