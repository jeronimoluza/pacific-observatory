"""Engrup (Andorra) -- https://engrup.com/.

Andorran consumer-electronics shop (AD500 Andorra la Vella, +376). OpenCart
(Journal3) with clean-SEO category URLs, so the ten top-level departments from
the homepage nav are listed explicitly. Cards are `div.product-thumb` with
`.price-normal` / `.price-new` prices, handled by the shared base. Do NOT add
`?limit=`: with it the theme rewrites every product href to
`.../limit-100.html`. Pagination is `?page=N` (12 cards per page, page 2
differs from page 1). Small catalogue (roughly 100 SKUs).
"""

from price_scraping.spiders._opencart_base import OpencartBaseSpider

_BASE = "https://engrup.com/"
_DEPARTMENTS = (
    "audio avisadores-de-radares cortadoras-de-pelo cámaras dj gps "
    "radio-frecuencia tablets telefonos televisión"
).split()


class EngrupAdSpider(OpencartBaseSpider):
    name = "engrup_ad"
    allowed_domains = ["engrup.com"]
    currency = "EUR"
    language = "es"
    CATEGORY_URLS = tuple(f"{_BASE}{d}/" for d in _DEPARTMENTS)
