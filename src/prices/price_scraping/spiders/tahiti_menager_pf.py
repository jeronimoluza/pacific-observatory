"""Tahiti Menager appliances and home goods WooCommerce feed."""

from __future__ import annotations

import logging

import requests

from ._woo_base import WooBaseSpider

logger = logging.getLogger(__name__)


class TahitiMenagerPfSpider(WooBaseSpider):
    name = "tahiti_menager_pf"
    allowed_domains = ["tahitimenager.pf", "www.tahitimenager.pf"]
    currency = "XPF"
    language = "fr"
    BASE_URL = "https://www.tahitimenager.pf/wp-json/wc/store/v1/products"

    async def start(self):
        session = requests.Session()
        session.headers.update({"User-Agent": self.custom_settings["USER_AGENT"]})
        page = 1
        while page <= 200:
            resp = session.get(self._page_url(page), timeout=30)
            resp.raise_for_status()
            products = resp.json()
            if not isinstance(products, list) or not products:
                break
            logger.info("%s page=%d count=%d", self.name, page, len(products))
            for product in products:
                item = self._item(product)
                if item:
                    yield item
            if len(products) < 100:
                break
            page += 1
