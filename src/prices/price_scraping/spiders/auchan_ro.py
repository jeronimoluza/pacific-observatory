"""Auchan Romania -- https://www.auchan.ro/. Full-line VTEX hypermarket.

CSV/round-1 labeled this "Custom/Enterprise" -- another platform
misidentification. robots.txt references VTEX-specific paths
(`/routing/vtex.store@2.x/`, `/salesforce/`), and the standard catalog
endpoint works directly on the custom domain (no myvtex.com bypass needed).
Re-verified live 2026-08-06: GET /api/catalog_system/pub/products/search
?_from=0&_to=9 -> HTTP 206, 107KB JSON, `resources: 0-9/59683` (59,683
total SKUs). Sample: 'Banane, +/- 1 kg' RON 6.99, 'Hartie igienica Auchan
16 role, 3 straturi' RON 25.99.
"""

from price_scraping.spiders._vtex_base import VtexBaseSpider


class AuchanRoSpider(VtexBaseSpider):
    name = "auchan_ro"
    allowed_domains = ["auchan.ro"]
    HOST = "www.auchan.ro"
    currency = "RON"
    language = "ro"
