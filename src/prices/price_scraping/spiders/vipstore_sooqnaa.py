"""
VIP Store (Syria) -- https://vipstore.sooqnaa.com/

sooqnaa.com-hosted storefront; see _sooqnaa_base.py for the shared flight-
payload contract and the measurement notes.

MEASURED 2026-09-12: /ar/products flight payload reports total=107; page 1
vs page 2 disjoint apart from the site-wide "latest products" strip
(32 + 29 ids, 3 shared).

CURRENCY: USD -- this store's own "currency" field reads "USD" while the
other three sooqnaa stores onboarded in the same pass read "SYP". Taken
from the payload, NOT from countries.yaml's SYP default: the catalog is
digital top-ups and subscription codes, which Syrian sellers price in USD.

CATALOG (MEASURED, 107-row run): handsets and accessories dominate
(Xiaomi 17, Samsung 8, Apple 2, Honor 1, mobile devices 6, phone repair
6); the digital tail is games 20, subscriptions 16, apps 14, currency
and credit 6, digital cards 6, money transfer 2. Spans COICOP 08.2, 08.3,
09.4 and 13.x, so coicop_codes is left unset.

Page family: listing.
"""

from price_scraping.spiders._sooqnaa_base import SooqnaaBaseSpider


class VipstoreSooqnaaSpider(SooqnaaBaseSpider):
    name = "vipstore_sooqnaa"
    allowed_domains = ["vipstore.sooqnaa.com"]
    STORE_HOST = "vipstore.sooqnaa.com"
    currency = "USD"
    language = "ar"
