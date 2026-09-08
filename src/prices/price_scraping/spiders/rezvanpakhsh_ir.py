"""
Rezvan Pakhsh Azimi (rezvanpakhsh.com) — Iranian food/FMCG wholesale
distributor (بنکداری و پخش عمده مواد غذایی), WooCommerce store.

Verified live 2026-09-05: /wp-json/wc/store/v1/products (WooCommerce Store
API) is open, no auth, paginates cleanly (X-WP-Total: 3428, 429 pages at
per_page=8; page 2 returns a fully distinct id set). Unlike every other
Iranian source in this repo, prices.currency_code is already "IRR" and the
product page quotes ریال (Rial) — 7 occurrences, zero تومان — so NO
Toman->Rial scaling applies here and neither FORCE_CURRENCY nor
PRICE_MULTIPLIER is set. Confirmed on the first row: رطب کبکاب کارتنی
1ک12ع at 31,359,708 ﷼ on both the API and the rendered PDP.

Catalog is genuine food-and-beverage with an FMCG tail: dates (رطب),
honey, chocolate, plus household cleaners and tissue. Wholesale carton
pricing (names carry the case count, e.g. "1ک12ع" = 1 kg x 12 units), so
these are case prices, not shelf prices — the analytical value is the
wholesale layer for Iran, where the repo previously had only two food
sources (hastmarket_ir, royalnuts_ir) against 21 cosmetics/pharmacy ones.

Page family parsed: API (Store API JSON; the spider never fetches a PDP).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class RezvanpakhshIrSpider(WooBaseSpider):
    name = "rezvanpakhsh_ir"
    allowed_domains = ["rezvanpakhsh.com"]
    currency = "IRR"
    language = "fa"
    BASE_URL = "https://rezvanpakhsh.com/wp-json/wc/store/v1/products"
