"""
Spider for Courts Guyana (Unicomer Group) -- https://www.courts.com/guyana/.

Sibling of courts_jm.py -- see that file's docstring for the full platform
writeup (shared Magento instance, 11 country storefronts + Omni Curacao,
store-scoped REST required to get real per-country prices past the
999999/9999999/0 default-scope sentinel). This file covers Guyana
(store code sc_guyana_sv, GYD).
"""

import logging

import scrapy

from price_scraping.spiders._magento_base import MagentoRestBaseSpider

logger = logging.getLogger(__name__)

_STORE_CODE = "sc_guyana_sv"
_SENTINEL_PRICES = {0, 999999, 9999999}


class CourtsGySpider(MagentoRestBaseSpider):
    name = "courts_gy"
    allowed_domains = ["courts.com"]
    currency = "GYD"
    language = "en"

    BASE_URL = "https://www.courts.com"
    PDP_BASE_URL = "https://www.courts.com/guyana/"
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
