"""
Shirin confectionery factory (Tajikistan) — https://shirin.tj/.

"Фабрика «Ширин» — Кондитерская корпорация", Dushanbe (address on
/contacts/: "Республика Таджикистан, г. Душанбе, 734002, улица Джаббора
Расулова"). A manufacturer's own storefront, so the catalogue is narrow by
construction: 35 SKUs, all sugar confectionery — ирис, карамель, мармелад,
помадка, шоколадные драже, мультизлаковая конфета, chocolate-coated nuts
and fruit.

WordPress 6.5.8 + WooCommerce 5.9.0, standard public Store API — but on the
**un-versioned** namespace: `/wp-json/wc/store/products` works,
`/wp-json/wc/store/v1/products` 404s. The rendered `/catalog/` page does not
paginate server-side (it hydrates client-side), so the API is the only
enumerable surface.

Enumerability confirmed 2026-09-05: `X-WP-Total: 35`, `X-WP-TotalPages: 4`
at per_page=10, and page 1 (ids 2559/2528/2520/2496…) and page 2
(ids 2277/2275/2267/2190…) are disjoint. At the base class's per_page=100
the whole catalogue is one request.

**Currency override is load-bearing.** The Store API reports
`prices.currency_code: "ABC"` — a placeholder left in the WooCommerce
settings, not a real ISO 4217 code — so the base class's `reported`
currency would poison every row. `FORCE_CURRENCY = "TJS"` pins it to the
somoni, which matches countries.yaml and the price levels (Chocofit ассорти
2800 at currency_minor_unit=2 -> 28.00 TJS).

Parses: API (the JSON Store API; no page is ever fetched at collection
time). `parse_html` for archived captures is inherited from the base class.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class ShirinTjSpider(WooBaseSpider):
    name = "shirin_tj"
    allowed_domains = ["shirin.tj"]
    currency = "TJS"
    language = "ru"
    BASE_URL = "https://shirin.tj/wp-json/wc/store/products"
    FORCE_CURRENCY = "TJS"
