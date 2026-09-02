"""
Hastmarket (hastmarket.ir) — Iranian online supermarket, WooCommerce store.

Verified live 2026-09-01: /wp-json/wc/store/v1/products (WooCommerce Store
API) is open, no auth, paginates cleanly (X-WP-Total: 8610 at per_page=1).
prices.currency_code returns "IRT" (Toman, non-ISO) with currency_minor_unit
0 -- 1 Toman = 10 Rial, so FORCE_CURRENCY="IRR" + PRICE_MULTIPLIER=10 report
the scraped Toman value as Rial, matching the adibmarket_ir/torob_ir
convention already used for other Iranian sources in this repo (IRR is the
only ISO 4217 code for Iran; Toman has none). Catalog is genuine grocery:
sampled products include Nutella spread, cheese, flour, spices, snacks,
drinks — real food-and-beverage SKUs, not a cosmetics-adjacent store.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class HastmarketIrSpider(WooBaseSpider):
    name = "hastmarket_ir"
    allowed_domains = ["hastmarket.ir"]
    currency = "IRR"
    language = "fa"
    BASE_URL = "https://hastmarket.ir/wp-json/wc/store/v1/products"
    FORCE_CURRENCY = "IRR"
    PRICE_MULTIPLIER = 10
    PRICE_MULTIPLIER_CURRENCY = "IRT"
