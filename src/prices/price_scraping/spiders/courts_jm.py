"""
Spider for Courts Jamaica (Unicomer Group) -- https://www.courts.com/jamaica/.

shopcourts.com 301-redirects to courts.com -> www.courts.com, a single
shared multi-website Magento 2 instance (Unicomer Group). GET
/rest/V1/store/storeConfigs (open, unauthenticated) lists 11 SEPARATE
Caribbean-country storefronts (Antigua, Barbados, Belize, Dominica,
Grenada, Guyana, Jamaica, St Kitts and Nevis, St Lucia, St Vincent,
Trinidad and Tobago) plus a distinct "Omni" Curacao banner on
shopomni.com, each its own Magento store_code/website with its own
currency -- not one storefront. /graphql is closed (403 "GraphQL
disabled"). The unscoped /rest/V1/products surface is open but returns
each product's *default*-scope price, which for most SKUs is a
999999/9999999/0 sentinel meaning "not sold in the default view" rather
than a real price. Store-scoped requests at
/rest/<store_code>/V1/products DO carry real, independently-priced
per-country data (verified live 2026-08-17: SKU T1827SP priced at 40 TTD
on the Trinidad storefront while showing the 9999999 sentinel on
Jamaica/Barbados/Guyana). `_item` drops the sentinel values. One spider
per country storefront, matching this repo's existing multi-country
convention (jarir_qa/jarir_kw/jarir_bh/jarir_ae/jarir_sa).

candidate_countries from the onboarding shard were Barbados, Guyana,
Jamaica, Trinidad and Tobago -- all four are real, live storefronts here;
this file covers Jamaica (store code sc_jamaica_sv, JMD). Siblings:
courts_bb.py, courts_gy.py, courts_tt.py.
"""

import logging

import scrapy

from price_scraping.spiders._magento_base import MagentoRestBaseSpider

logger = logging.getLogger(__name__)

_STORE_CODE = "sc_jamaica_sv"
_SENTINEL_PRICES = {0, 999999, 9999999}


class CourtsJmSpider(MagentoRestBaseSpider):
    name = "courts_jm"
    allowed_domains = ["courts.com"]
    currency = "JMD"
    language = "en"

    BASE_URL = "https://www.courts.com"
    PDP_BASE_URL = "https://www.courts.com/jamaica/"
    PAGE_SIZE = 200
    MAX_PAGES = 300

    def _page_request(self, page: int):
        url = (
            f"{self.BASE_URL}/rest/{_STORE_CODE}/V1/products"
            f"?searchCriteria%5BpageSize%5D={self.PAGE_SIZE}"
            f"&searchCriteria%5BcurrentPage%5D={page}"
        )
        return scrapy.Request(
            url,
            callback=self.parse_page,
            meta={"page": page},
            headers={"Accept": "application/json"},
        )

    def parse_page(self, response):
        # Override _magento_base's continuation check: it stops as soon as
        # one page returns fewer than PAGE_SIZE items, which stalls early on
        # this 22k-SKU shared catalog since most items are sentinel-priced
        # for any given store and short-but-not-final pages are common.
        # Use the REST response's own `total_count` instead.
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON response at {response.url}")
            return
        items = data.get("items") or []
        total_count = data.get("total_count") or 0
        page = response.meta["page"]
        logger.info(
            f"{self.name}: page={page} count={len(items)} total_count={total_count}"
        )
        for p in items:
            item = self._item(p)
            if item:
                yield item
        if page * self.PAGE_SIZE < total_count and page < self.MAX_PAGES:
            yield self._page_request(page + 1)

    def _item(self, p: dict):
        if p.get("price") in _SENTINEL_PRICES:
            return None
        item = super()._item(p)
        if item and item["url"]:
            item["url"] = item["url"].replace(f"{self.BASE_URL}/", self.PDP_BASE_URL)
        return item
