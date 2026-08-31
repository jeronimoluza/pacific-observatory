"""
Solomon's Fresh Market — Harbour Bay (Nassau, The Bahamas).
https://www.solomonsfreshmarkets.com/ -> redirects to
https://harborbaymarkets.storebyweb.com/s/1000-19/.

Solomon's Fresh Market is a supermarket chain of AML Foods Ltd., a
Bahamian public company (Bahamas International Securities Exchange:
AML) headquartered in Nassau; its online-ordering platform serves pickup
and mailboat/delivery only within The Bahamas (see
https://www.amlfoods.com/, thenassauguardian.com coverage of the launch).
Not a diaspora/US storefront -- this is the retailer's own live catalog
and shelf pricing for its Harbour Bay location.

See _storebyweb_base.py for the shared "storebyweb" (WebCart) platform
API. Verified live 2026-08-31: POST /api/b {"pn":N,"ps":100,"facets":{}}
totalCount=11359; 5 consecutive 100-row pages returned 500/500 distinct
ids (zero overlap), 0% zero/null-price rows in a 500-row sample, price
range $0.69-$44.99. Item-detail route /i/<id> is server-rendered with the
product name in <title>/og:title, confirmed on 3 spot-checked ids.
"""

from price_scraping.spiders._storebyweb_base import StorebywebBaseSpider


class SolomonsfreshmarketsBsSpider(StorebywebBaseSpider):
    name = "solomonsfreshmarkets_bs"
    allowed_domains = ["harborbaymarkets.storebyweb.com"]
    currency = "BSD"
    language = "en"
    BASE_HOST = "harborbaymarkets.storebyweb.com"
    STORE_CODE = "1000-19"
