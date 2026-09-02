"""
Exuma Markets — Great Exuma, The Bahamas (a Family Island, outside Nassau).
https://www.exumamarkets.com/ -> redirects to
https://exumamarkets.storebyweb.com/s/1000-11/.

Another AML Foods Ltd. chain on the same "storebyweb" (WebCart) platform
as solomonsfreshmarkets_bs / costrightnassau_bs (see _storebyweb_base.py
and amlfoods.com/eleuthera-markets/ etc. for the group's Family Island
footprint). Included deliberately as a *different island* rather than a
third Nassau storefront: Family Island grocery prices in the Bahamas run
materially higher than New Providence due to inter-island freight, so this
captures a real, distinct price series rather than padding the source
count with a duplicate catalog.

Verified live 2026-08-31: POST /api/b {"pn":N,"ps":100,"facets":{}}
totalCount=5028; 4 pages of ps=100 returned 400/400 distinct ids, 0%
zero/null-price rows, price range $0.50-$33.99.
"""

from price_scraping.spiders._storebyweb_base import StorebywebBaseSpider


class ExumamarketsBsSpider(StorebywebBaseSpider):
    name = "exumamarkets_bs"
    allowed_domains = ["exumamarkets.storebyweb.com"]
    currency = "BSD"
    language = "en"
    BASE_HOST = "exumamarkets.storebyweb.com"
    STORE_CODE = "1000-11"
