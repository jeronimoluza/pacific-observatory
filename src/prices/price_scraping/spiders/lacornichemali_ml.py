"""
La Corniche Mali (Bamako) — https://lacornichemali.com/.

Standard WooCommerce Store API on the versioned route (WordPress 6.6.7,
WooCommerce 9.8.7, "Freshio" grocery theme). Verified live 2026-09-01:
1045 products; category breakdown is heavily food-weighted (Épicerie 247,
Épicerie salée 131, Épicerie sucrée 112, Boissons 72, Boissons chaudes 74,
Café 40, Conserve 41, Jus de fruits et de légumes 45, Céréales 30, Laits
23, Fruits et légumes 13, Boucherie 12, Boulangerie 6, Fromages 2 — vs a
much smaller non-food tail: Douche/savon 38, Dentaire 22, Entretien,
hygiène papier 113, Hygiène et Beauté 1). currency_minor_unit=0 confirmed
in the Store API payload (XOF has no minor unit — matches the Mali brief's
currency trap).

DEMO-DATA TRAP: ~30 of 1044 listings are leftover WooCommerce "Freshio"
theme demo/seed products (Faker-generated names like "Intelligent Leather
Plate", "Sleek Bronze Shoes"), all tagged with the literal category
"Freshio Category" — not real Corniche Mali catalog items. Filtered out
by category name below; everything else in the catalog carries real
French product names and categories.
"""

from price_scraping.spiders._woo_base import WooBaseSpider

_DEMO_CATEGORY = "Freshio Category"


class LacornichemaliMlSpider(WooBaseSpider):
    name = "lacornichemali_ml"
    allowed_domains = ["lacornichemali.com"]
    currency = "XOF"
    language = "fr"
    BASE_URL = "https://lacornichemali.com/wp-json/wc/store/v1/products"

    def _item(self, p: dict):
        cats = p.get("categories") or []
        if any(c.get("name") == _DEMO_CATEGORY for c in cats if isinstance(c, dict)):
            return None
        # A handful of listings carry a literal 0 price (display-only /
        # out-of-stock rows). A zero price is never a usable observation.
        row = super()._item(p)
        if row is None or float(row["price"] or 0) == 0:
            return None
        return row
