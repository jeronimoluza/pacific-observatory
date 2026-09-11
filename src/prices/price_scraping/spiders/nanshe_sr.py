"""
Nanshe (Suriname) -- https://nanshe.sr/.

WooCommerce Store API, non-standard install: /wp-json/ 404s on this
tenant (confirmed 2026-09-11), but the API is live via the
?rest_route= query-string form -- "https://nanshe.sr/?rest_route=/wc
/store/v1/products" returns 200 JSON (per the fallback documented in
_woo_base.py's module docstring). Home electronics/appliances catalog
('Samsung Television', 'Oster Iron', 'Kitchen Elite Air Fryer',
'Hamilton Beach Toaster', various Conair hair-care and Brentwood kitchen
appliances) -- classified electronics. Matches the brief's fingerprint-
only 'high quality / low prices' tagline; the actual catalog is branded
small appliances / consumer electronics.

Verified live 2026-09-11: x-wp-total=1293, x-wp-totalpages=1293 at
per_page=1 (i.e. 1,293 products, ~65 pages at per_page=20). Page 1 vs
page 2 (per_page=20) returned disjoint product-id sets, zero overlap --
genuine pagination.

Currency: Store API reports currency_code=SRD -- matches Suriname's
country currency.

Page family: API (Store API JSON; product permalinks are
"?product=<slug>" query-string URLs, never fetched by this spider).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class NansheSrSpider(WooBaseSpider):
    name = "nanshe_sr"
    allowed_domains = ["nanshe.sr", "www.nanshe.sr"]
    currency = "SRD"
    language = "nl"
    BASE_URL = "https://nanshe.sr/?rest_route=/wc/store/v1/products"
