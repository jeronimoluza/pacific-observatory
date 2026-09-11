"""
Daymarket (Niger) -- https://daymarket.net/ ("votre supermarche").

Standard WooCommerce Store API. XOF prices at currency_minor_unit=0 (XOF
has no decimal subunit -- "500" -> 500 XOF, no division), currency_code
confirmed as "XOF" directly from the Store API response.

Small but broad catalog: 81 SKUs total (per_page=50 page 1 -> 50, page 2 ->
31, page 3 empty), spanning beverages, bottled gas, dairy, produce, bakery,
personal care and confectionery -- multiple COICOP divisions in one small
grocer, exactly the breadth this campaign is targeting.

Enumerability confirmed: per_page=50 page 1 vs page 2 -> 0 id overlap.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class DaymarketNeSpider(WooBaseSpider):
    name = "daymarket_ne"
    allowed_domains = ["daymarket.net"]
    currency = "XOF"
    language = "fr"
    BASE_URL = "https://daymarket.net/wp-json/wc/store/v1/products"
