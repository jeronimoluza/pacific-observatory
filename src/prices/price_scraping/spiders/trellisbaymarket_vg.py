"""
Trellis Bay Market (British Virgin Islands) -- https://trellisbaymarket.com/.

Small physical mini-market and yacht-provisioning business at Trellis Bay,
Beef Island, Tortola, BVI -- "has taken their mini-market online with
delivery" (confirmed via web search and the site's own /orders/ page).

Standard WooCommerce Store API (/wp-json/wc/store/v1/products), no auth.
currency_minor_unit=2. Verified live 2026-09-11: X-WP-Total 7 -- the whole
online catalog is small (this is genuinely a mini-market's online order
form, not a full supermarket), spanning Grocery, Fresh Produce, Snacks and
Cigarette categories. Below the usual "worth a spider" catalog size but
still clears the >=5-row Phase 6 gate and adds tobacco (COICOP 02.4) and
dairy (COICOP 01.4) SKUs alongside riteway_vg, the other BVI source.

Currency: Store API's own currency_code field reports USD on every
product -- matches BVI's official currency (USD; the BVI has no local
currency of its own).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class TrellisbaymarketVgSpider(WooBaseSpider):
    name = "trellisbaymarket_vg"
    allowed_domains = ["trellisbaymarket.com"]
    currency = "USD"
    language = "en"
    FORCE_CURRENCY = "USD"
    BASE_URL = "https://trellisbaymarket.com/wp-json/wc/store/v1/products"
