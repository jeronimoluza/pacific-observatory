"""
Glow Haven (Syria) -- https://glowhaven.sy/.

Standard WooCommerce Store API. Fragrances and skincare (e.g. 'Sweet Pea
Body Lotion by Bath & Body Works') -- classified cosmetics.

Verified live 2026-09-11: x-wp-total=806, x-wp-totalpages=41 at
per_page=20. Page 1 vs page 2 returned disjoint product-id sets, zero
overlap -- genuine pagination.

Currency: Store API reports currency_code=USD consistently -- spread-
checked pages 1, 10, 20, 30, 41 (spanning the full catalog, ~120 products
sampled), all USD, zero SYP. Confirmed genuine (imported branded
fragrances/skincare priced in USD is expected for this segment), not a
display artifact. No FORCE_CURRENCY needed. currency_minor_unit=2 (e.g.
price "1700" -> USD 17.00).

Page family: API (Store API JSON; permalinks are real PDP URLs but never
fetched by this spider).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class GlowhavenSySpider(WooBaseSpider):
    name = "glowhaven_sy"
    allowed_domains = ["glowhaven.sy", "www.glowhaven.sy"]
    currency = "USD"
    language = "ar"
    BASE_URL = "https://glowhaven.sy/wp-json/wc/store/v1/products"
