"""
Telesur (Suriname) — https://www.telesur.sr/.

National telecom's device/accessories shop (phones, chargers, cases,
routers). Bare domain 301s the base path away from /wp-json/, so we hit the
www subdomain directly.

2 SKUs ("Opwaarderen" / "Beltegoed Opwaarderen" -- Dutch for "top up" /
"credit top-up") carry price=0 upstream: they're variable-amount prepaid
mobile-credit recharge products where the customer picks the amount at
checkout, not a fixed-price SKU. Confirmed live 2026-08-17. Dropped at the
spider rather than emitted as a 0-price row.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class TelesurSrSpider(WooBaseSpider):
    name = "telesur_sr"
    allowed_domains = ["www.telesur.sr"]
    currency = "SRD"
    language = "nl"
    BASE_URL = "https://www.telesur.sr/wp-json/wc/store/v1/products"

    def _item(self, p: dict):
        item = super()._item(p)
        if item and float(item["price"]) <= 0:
            return None
        return item
