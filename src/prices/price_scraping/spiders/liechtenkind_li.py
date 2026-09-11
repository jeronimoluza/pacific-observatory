"""
Liechtenkind -- https://www.liechtenkind.com/.

Natural handmade soaps, shower butter and candles (a small
Liechtenstein/Werdenberg-region cosmetics brand -- see e.g. "Naturwachs-
Kerze ... Ich brenne fuer Werdenberg"). Standard WooCommerce Store API,
CHF prices at currency_minor_unit=2 (e.g. "1240" -> CHF 12.40), confirmed
live 2026-09-11.

Enumerability confirmed: x-wp-total=75 across 4 pages (per_page=20).
page1 ids [12952,12695,11926,11773,11725] vs page2
[10963,10960,10953,10922,10832] -- disjoint, catalog paginates cleanly.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class LiechtenkindLiSpider(WooBaseSpider):
    name = "liechtenkind_li"
    allowed_domains = ["liechtenkind.com"]
    currency = "CHF"
    language = "de"
    BASE_URL = "https://www.liechtenkind.com/wp-json/wc/store/v1/products"
