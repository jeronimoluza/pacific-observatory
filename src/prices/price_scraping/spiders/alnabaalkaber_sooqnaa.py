"""
Al-Naba Al-Kaber (Syria) -- https://alnabaalkaber.sooqnaa.com/

sooqnaa.com-hosted storefront; see _sooqnaa_base.py for the shared flight-
payload contract and the measurement notes.

MEASURED 2026-09-12: /ar/products flight payload reports total=54; page 1
vs page 2 disjoint apart from the site-wide "latest products" strip
(29 + 28 ids, 2 shared).

CURRENCY: SYP, read from this store's own "currency":"SYP" in the flight
payload on 2026-09-12.

CATALOG (MEASURED, 54-row run, wider than the discovery note's
"appetisers"): appetisers 14, grills 13, salads 10, drinks 8, premium
appetisers 7, shisha 2 -- with imported beer, alcohol-free beer, energy
drinks, juice and cola among the drinks. Spans COICOP 11.1.1 (catering),
02.1 (alcohol), 01.2 (soft drinks) and 02.3 (tobacco/shisha), so
coicop_codes is left unset.

Page family: listing.
"""

from price_scraping.spiders._sooqnaa_base import SooqnaaBaseSpider


class AlnabaalkaberSooqnaaSpider(SooqnaaBaseSpider):
    name = "alnabaalkaber_sooqnaa"
    allowed_domains = ["alnabaalkaber.sooqnaa.com"]
    STORE_HOST = "alnabaalkaber.sooqnaa.com"
    currency = "SYP"
    language = "ar"
