"""
Amani Bookstore (Syria) -- https://amanibook.sooqnaa.com/

sooqnaa.com-hosted storefront; see _sooqnaa_base.py for the shared flight-
payload contract and the measurement notes.

MEASURED 2026-09-12: /ar/products flight payload reports total=107;
24 products per page, page 1 vs page 2 disjoint apart from the site-wide
"latest products" strip. Sample product: "هسريك فيكسيوس (فن قراءة العقول)"
at 550, is_in_stock true.

CURRENCY: SYP, read from this store's own "currency":"SYP" in the flight
payload on 2026-09-12.

CATALOG: books -- novels, poetry diwans, self-help and business titles.

Page family: listing.
"""

from price_scraping.spiders._sooqnaa_base import SooqnaaBaseSpider


class AmanibookSooqnaaSpider(SooqnaaBaseSpider):
    name = "amanibook_sooqnaa"
    allowed_domains = ["amanibook.sooqnaa.com"]
    STORE_HOST = "amanibook.sooqnaa.com"
    currency = "SYP"
    language = "ar"
