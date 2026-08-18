"""
Spider for Gollo (Costa Rica) -- https://www.gollo.com/.

Magento SSR storefront. GraphQL (/graphql) is explicitly disabled
(403 "GraphQL disabled", served by Varnish) -- confirmed live
2026-08-17 -- so this uses MagentoSSRBaseSpider (data-price-amount /
product-item-link markup in the rendered category HTML) rather than the
GraphQL base. Discovery walks the 15 top-level nav categories on the
homepage; standard Magento ?p=N pagination.

Two fixes over the base's defaults, both confirmed live 2026-08-17:
- Every gollo.com PDP URL ends in a literal `/p` path segment (e.g.
  `.../celular-motorola-motorola-g06-.../p`), so the base `_item`'s
  `url.rsplit("/", 1)[-1]` product_id extraction collapses every product
  to the literal string "p" -- a silent all-rows-collide dedup bomb.
  Overridden here to use the slug segment before `/p` instead.
- The base's `_item` hardcodes `category: None`; overridden to stamp the
  category slug from the listing page's own URL (e.g. "c/electrodomesticos"
  -> "electrodomesticos").
"""

import re

import scrapy

from price_scraping.spiders import _magento_base
from price_scraping.spiders._magento_base import MagentoSSRBaseSpider


class GolloCrSpider(MagentoSSRBaseSpider):
    name = "gollo_cr"
    allowed_domains = ["gollo.com"]
    currency = "CRC"
    language = "es"

    DISCOVERY_URL = "https://www.gollo.com/"
    CATEGORY_URL_RE = re.compile(r'href="(https://www\.gollo\.com/c/[a-z0-9\-]+)"')
    PAGE_PARAM = "p"
    MAX_PAGES = 20

    def parse_listing(self, response):
        body = response.text
        page = response.meta["page"]
        base = response.meta["base"]
        category = base.rstrip("/").rsplit("/", 1)[-1].replace("-", " ")
        matches = _magento_base._PRODUCT_BLOCK_RE.findall(body)
        for url, name, price in matches:
            item = self._item(url, name, price)
            if item:
                item["category"] = category
                yield item
        if matches and page < self.MAX_PAGES:
            sep = "&" if "?" in base else "?"
            nxt = page + 1
            yield scrapy.Request(
                f"{base}{sep}{self.PAGE_PARAM}={nxt}",
                callback=self.parse_listing,
                meta={"page": nxt, "base": base},
            )

    def _item(self, url: str, name: str, price: str):
        item = super()._item(url, name, price)
        if item:
            parts = url.rstrip("/").split("/")
            item["product_id"] = (
                parts[-2] if len(parts) >= 2 and parts[-1] == "p" else parts[-1]
            )
        return item
