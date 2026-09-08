"""
Ehsan Market (ehsanmarket.shop) — Iranian online food retailer specialising
in imported groceries and confectionery (خوراکی‌های خارجی), WooCommerce
store.

Verified live 2026-09-05: /wp-json/wc/store/v1/products (WooCommerce Store
API) is open, no auth, paginates cleanly (X-WP-Total: 1770; page 2 returns
a fully distinct id set). prices.currency_code returns "IRT" (Toman,
non-ISO) with currency_minor_unit 0, and the rendered PDP quotes تومان
(5 occurrences, zero ریال) — so FORCE_CURRENCY="IRR" and
PRICE_MULTIPLIER=10 report the scraped Toman value as Rial, the convention
already used by adibmarket_ir / hastmarket_ir / royalnuts_ir / torob_ir.
STORED VALUE IS RIAL (IRR), scaled x10 from the site's Toman price.

Catalog sampled at build time is ~all division-01: instant coffee, coconut
milk, chocolate, breakfast spread, Nespresso capsules, desserts/snacks.

Page family parsed: API (Store API JSON; the spider never fetches a PDP).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class EhsanmarketIrSpider(WooBaseSpider):
    name = "ehsanmarket_ir"
    allowed_domains = ["ehsanmarket.shop"]
    currency = "IRR"
    language = "fa"
    BASE_URL = "https://ehsanmarket.shop/wp-json/wc/store/v1/products"
    FORCE_CURRENCY = "IRR"
    PRICE_MULTIPLIER = 10
    PRICE_MULTIPLIER_CURRENCY = "IRT"
