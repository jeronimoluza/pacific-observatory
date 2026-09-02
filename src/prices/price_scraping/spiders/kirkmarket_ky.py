"""
Spider for Kirk Market (Grand Cayman) — https://kirkmarket.ky/.

Standard WooCommerce Store API (/wp-json/wc/store/v1/products), 40 total
products across 6 categories (Appetizer/Party/Charcuterie/Bakery Platters,
Cakes, Pastries) — verified live via `GET
kirkmarket.ky/wp-json/wc/store/v1/products?per_page=1` -> X-WP-Total: 40.

This is Kirk Market's online catering/special-orders shop, not a full
everyday-grocery aisle catalogue — kirkmarket.ky has no per-SKU browsing
for its regular supermarket shelf (unlike Foster's/Freshop). The channel
is genuinely `specialty-food` (pre-made platters, cakes, pastries sold as
a catering SKU catalogue), not `supermarket` — labelled honestly rather
than inflated, per onboarding rules.

Currency: KYD, taken directly from the API's own
`prices.currency_code` field (not inferred from the "$" symbol) —
verified live: "Gourmet Mini Chicken Sliders" prices.currency_code="KYD",
price="4999" (minor_unit=2 -> $49.99 CI).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class KirkmarketKySpider(WooBaseSpider):
    name = "kirkmarket_ky"
    allowed_domains = ["kirkmarket.ky"]
    currency = "KYD"
    language = "en"

    BASE_URL = "https://kirkmarket.ky/wp-json/wc/store/v1/products"
