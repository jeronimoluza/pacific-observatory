"""
Spider for VkusVill (Russia) — https://www.vkusvill.ru/ national grocery chain.

Server-rendered Bitrix storefront. Both category *listing* pages
(/goods/<category>/) and product detail pages embed a clean Schema.org
JSON-LD block; the listing page's block is a `@graph` array carrying every
product card shown on that page (name, sku, price, priceCurrency,
availability, canonical url) — no need to visit individual PDPs at all.

Category discovery: /goods/ lists ~44 top-level department links
(dairy/meat/fish/veg/bread/sweets/alcohol/household/pet, etc — this is a
full grocery assortment, not a niche shop). Each department paginates with
Bitrix's `?PAGEN_1=N`; the page-1 response's own pager block
(`.VV_Pager__Item[data-page]`) gives the true last page number for that
department, so pages are walked from the server's own count rather than a
guessed `next` link or a fixed cap. A pre-flight scout of all 44
departments (2026-09-01) found real, distinct-content pagination up to
page 161 (svezhie-tsvety/flowers) and a sum of 1,220 pages across
departments (~29k products before cross-category dedup by url/product_id)
-- confirmed by comparing page 1 and page 161 of the flowers department
and finding entirely different product sets on each, not a repeat. That
total is small enough to walk in full, so there is no page cap: every
department's listing is walked to its own reported last page.

No city/store cookie was required to see prices (checked cold, no
`?city=`/geolocation cookie set) — vkusvill.ru appears to serve one
national online price list rather than per-store pricing.
"""

import html
import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.vkusvill.ru"
GOODS_INDEX = f"{BASE_URL}/goods/"

# Top-level department slugs only (single path segment under /goods/).
_TOP_CATEGORY_RE = re.compile(r"^/goods/[a-z0-9-]+/$")

_WHITESPACE_RE = re.compile(r"\s+")


def _clean_text(value: str) -> str:
    """Unescape HTML entities and collapse all whitespace (incl. NBSP) to a
    single plain space. html.unescape("&nbsp;") returns "\xa0" (U+00A0),
    not a regular space, so the entity decode alone leaves a distinct
    codepoint in the text that a naive `.strip()` does not remove and that
    reads as a different token than a plain space downstream (tokenisation,
    dedup keys, the COICOP classifier). `\s` matches `\xa0` under Python's
    Unicode default, so one re.sub pass after unescape fixes it.
    """
    return _WHITESPACE_RE.sub(" ", html.unescape(value)).strip()


class VkusvillRuSpider(scrapy.Spider):
    name = "vkusvill_ru"
    allowed_domains = ["vkusvill.ru", "www.vkusvill.ru"]
    currency = "RUB"
    language = "ru"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            GOODS_INDEX, callback=self.parse_index, errback=self.errback
        )

    def parse_index(self, response):
        hrefs = sorted(set(response.css('a[href^="/goods/"]::attr(href)').getall()))
        categories = sorted({h for h in hrefs if _TOP_CATEGORY_RE.match(h)})
        logger.info(f"{self.name}: top-level categories found={len(categories)}")
        for href in categories:
            slug = href.strip("/").rsplit("/", 1)[-1]
            yield response.follow(
                href,
                callback=self.parse_listing,
                errback=self.errback,
                meta={"category": slug, "page": 1},
            )

    def parse_listing(self, response):
        category = response.meta["category"]
        page = response.meta["page"]
        products = self._extract_products(response)

        found = 0
        for prod in products:
            offer = prod.get("offers") or {}
            if isinstance(offer, list):
                offer = offer[0] if offer else {}
            price = offer.get("price")
            name = prod.get("name")
            if price is None or not name:
                continue
            found += 1
            yield {
                "product_id": str(prod.get("sku") or offer.get("url") or ""),
                "product_name": _clean_text(str(name))[:500],
                "category": _clean_text(category) if category else category,
                "price": str(price),
                "currency": offer.get("priceCurrency") or self.currency,
                "available": "InStock" in str(offer.get("availability") or ""),
                "url": offer.get("url") or response.url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        logger.info(
            f"{self.name}: {response.url} category={category} page={page} "
            f"products={len(products)} yielded={found}"
        )

        if page == 1:
            last_page = self._last_page(response)
            for n in range(2, last_page + 1):
                yield response.follow(
                    f"{response.url}?PAGEN_1={n}",
                    callback=self.parse_listing,
                    errback=self.errback,
                    meta={"category": category, "page": n},
                )

    @staticmethod
    def _last_page(response):
        pages = response.css(".VV_Pager__Item::attr(data-page)").getall()
        nums = [int(p) for p in pages if p.isdigit()]
        return max(nums) if nums else 1

    @staticmethod
    def _extract_products(response):
        out = []
        for raw in response.xpath(
            '//script[@type="application/ld+json"]/text()'
        ).getall():
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            candidates = (
                data.get("@graph")
                if isinstance(data, dict) and "@graph" in data
                else [data]
            )
            for c in candidates:
                if isinstance(c, dict) and c.get("@type") == "Product":
                    out.append(c)
        return out

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
