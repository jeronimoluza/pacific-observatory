"""sas.am — SAS Supermarket (Armenia), custom Bitrix-style storefront.

Verified live 2026-09-01. Category list comes from
``https://www.sas.am/sitemap.xml`` -> ``sitemap-custom-catalog-sections.xml``,
filtered to the root (no locale prefix) ``/catalog/<slug>/`` entries (627
distinct flat categories, no parent/child path nesting to dedupe). The
unprefixed root path is the site's **Armenian**-language version (product
names in Armenian script, e.g. "Պանիր լոռի «Դիլի»"); ``/en/catalog/...`` and
``/ru/catalog/...`` siblings exist with identical ids/prices but
English/Russian names. Armenian is used here per the onboarding brief
(classifier wants the real product-name language), even though our tier-a
regex support for ``hy`` may still be thin. Each category page is
server-rendered with product cards (``div.product.js-product``) carrying:

- ``product_name``: ``div.product__name`` text (two duplicate nodes for
  responsive layout, first one used).
- ``product_id``: ``input[name=id]`` inside the card's ``product__form`` —
  matches the numeric id in the PDP URL
  (``/en/catalog/<slug>/<id>/``).
- ``price``: ``div.price__new span.price__text`` text node, e.g.
  ``"1\\xa0545 "`` — AMD integers with a non-breaking-space thousands
  separator, no decimal subunit (dram/luma is obsolete; do NOT divide by
  100). Digits are extracted with a regex that strips everything else.
- ``category``: the page's ``h1.page-title__value`` text with the
  trailing ``"(<count>)"`` note stripped.

Pagination is offset-based (``?offset=24``, ``?offset=48``, ...) and is
**not self-terminating**: requesting an offset past the real last page
silently wraps back to page 1's content instead of returning empty
(confirmed live: offset=120 on a 112-item/5-page category returned the same
leading product ids as offset=0). The spider therefore tracks per-category
seen ids and stops once a page yields zero new ids, not on a short response
— the same trap documented in ``parma_am.py`` for the sister site.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_LOC_RE = re.compile(r"<loc>(http://sas\.am/catalog/[^<]+)</loc>")
_PAGE_SIZE = 24
_MAX_PAGES_PER_CATEGORY = 60


class SasAmSpider(scrapy.Spider):
    name = "sas_am"
    allowed_domains = ["sas.am", "www.sas.am"]
    currency = "AMD"
    language = "hy"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.4,
        "AUTOTHROTTLE_ENABLED": True,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(
            "https://www.sas.am/sitemap-custom-catalog-sections.xml",
            callback=self.parse_sitemap,
        )

    def parse_sitemap(self, response):
        urls = sorted({m for m in _LOC_RE.findall(response.text)})
        # normalize to https://www.sas.am
        paths = sorted({u.split("sas.am", 1)[1] for u in urls})
        logger.info("sas_am: %d categories from sitemap", len(paths))
        for path in paths:
            yield scrapy.Request(
                f"https://www.sas.am{path}",
                callback=self.parse_category,
                meta={"path": path, "offset": 0, "seen": set()},
            )

    def parse_category(self, response):
        path = response.meta["path"]
        offset = response.meta["offset"]
        seen: set = response.meta["seen"]

        cards = response.css("div.product.js-product")
        title = response.css("h1.page-title__value::text").get()
        category = re.sub(r"\s+", " ", (title or "").strip()) or None

        scraped_at = datetime.now(timezone.utc).isoformat()
        ids_this_page = []
        emitted = 0
        for card in cards:
            item = self._parse_card(card, response, category, scraped_at)
            if item is None:
                continue
            ids_this_page.append(item["product_id"])
            if item["product_id"] in seen:
                continue
            yield item
            emitted += 1

        new_ids = set(ids_this_page) - seen
        logger.info(
            "sas_am: path=%s offset=%s cards=%d new=%d",
            path,
            offset,
            len(cards),
            len(new_ids),
        )

        if new_ids and offset // _PAGE_SIZE < _MAX_PAGES_PER_CATEGORY:
            seen = seen | new_ids
            next_offset = offset + _PAGE_SIZE
            yield scrapy.Request(
                f"https://www.sas.am{path}?offset={next_offset}",
                callback=self.parse_category,
                meta={"path": path, "offset": next_offset, "seen": seen},
            )

    def _parse_card(self, card, response, category, scraped_at: str) -> dict | None:
        name = card.css("div.product__name::text").get()
        product_id = card.css("input[name=id]::attr(value)").get()
        href = card.css("a.product__cover-link::attr(href)").get()
        price_raw = card.css("div.price__new span.price__text::text").get()

        if not name or not product_id or not price_raw:
            return None

        digits = re.sub(r"[^\d]", "", price_raw)
        if not digits:
            return None

        name = re.sub(r"\s+", " ", name).strip()
        url = urljoin(response.url, href) if href else response.url

        return {
            "product_id": product_id,
            "product_name": name[:500],
            "category": category,
            "price": digits,
            "currency": self.currency,
            "available": True,
            "url": url,
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
