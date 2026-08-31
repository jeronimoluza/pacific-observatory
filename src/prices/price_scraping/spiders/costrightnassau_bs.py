"""
Cost Right Nassau — wholesale grocery/general-merchandise club (Nassau,
The Bahamas). https://www.costrightnassau.com/ -> redirects to
https://costrightnassau.storebyweb.com/s/1000-22/.

Cost Right is AML Foods Ltd.'s wholesale-club chain (same Bahamian public
company as Solomon's Fresh Market/Harbour Bay, see
solomonsfreshmarkets_bs.py); its online platform offers member pricing
consistent with the physical Nassau store, with delivery only within
The Bahamas or to a family-island mailboat.

Same "storebyweb" (WebCart) platform/API as solomonsfreshmarkets_bs
(see _storebyweb_base.py). Verified live 2026-08-31: POST /api/b
{"pn":N,"ps":100,"facets":{}} totalCount=332 (a real, smaller wholesale
assortment -- not a capped/broken catalog); 4 pages returned 332/332
distinct ids, 0% zero/null-price rows, price range $0.89-$1299.99.
"""

from price_scraping.spiders._storebyweb_base import StorebywebBaseSpider


class CostrightnassauBsSpider(StorebywebBaseSpider):
    name = "costrightnassau_bs"
    allowed_domains = ["costrightnassau.storebyweb.com"]
    currency = "BSD"
    language = "en"
    BASE_HOST = "costrightnassau.storebyweb.com"
    STORE_CODE = "1000-22"
