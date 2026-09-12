"""
ZAD / a14km (Syria) -- https://a14km.sooqnaa.com/

sooqnaa.com-hosted storefront; see _sooqnaa_base.py for the shared flight-
payload contract and the measurement notes.

MEASURED 2026-09-12: /ar/products flight payload reports total=30; page 1
vs page 2 disjoint apart from the site-wide "latest products" strip
(28 + 9 ids, 3 shared).

CURRENCY: SYP, read from this store's own "currency":"SYP" in the flight
payload on 2026-09-12.

CATALOG: books and study/religious texts, part of them digital
(is_digital true on some rows). The candidate note's "ZAD" (provisions)
branding is NOT a grocery signal -- the catalog is books, confirmed on
the live listing. Narrow: COICOP 09.7.1.

Page family: listing.
"""

from price_scraping.spiders._sooqnaa_base import SooqnaaBaseSpider


class A14kmZadSooqnaaSpider(SooqnaaBaseSpider):
    name = "a14km_zad_sooqnaa"
    allowed_domains = ["a14km.sooqnaa.com"]
    STORE_HOST = "a14km.sooqnaa.com"
    currency = "SYP"
    language = "ar"
