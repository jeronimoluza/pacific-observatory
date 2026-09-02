"""Farmboy Fiji WooCommerce storefront."""

from __future__ import annotations

import logging

import scrapy

from ._woo_base import MAX_PAGES, PER_PAGE, WooBaseSpider

logger = logging.getLogger(__name__)


class FarmboyFjSpider(WooBaseSpider):
    name = "farmboy_fj"
    allowed_domains = ["farmboyfiji.com"]
    BASE_URL = "https://farmboyfiji.com/wp-json/wc/store/v1/products"
    currency = "FJD"
    language = "en"
    IMPERSONATE_PROFILE = "chrome124"
    custom_settings = {
        **WooBaseSpider.custom_settings,
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
        },
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(
            self._page_url(1),
            callback=self.parse_page,
            meta={"page": 1, "impersonate": self.IMPERSONATE_PROFILE},
        )

    def parse_page(self, response):
        try:
            products = response.json()
        except ValueError:
            logger.warning("non-JSON response at %s", response.url)
            return
        if not isinstance(products, list) or not products:
            return
        page = response.meta["page"]
        logger.info("%s page=%s count=%s", self.name, page, len(products))
        for product in products:
            item = self._item(product)
            if item:
                yield item
        if len(products) >= PER_PAGE and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                self._page_url(nxt),
                callback=self.parse_page,
                meta={"page": nxt, "impersonate": self.IMPERSONATE_PROFILE},
            )
