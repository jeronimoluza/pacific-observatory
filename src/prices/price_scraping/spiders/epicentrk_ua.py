"""
Spider for Epicentr K (https://epicentrk.ua/) -- Ukraine's largest domestic
hardware/general big-box retail group (DIY, construction materials,
electronics, tools, tires, toys, sports goods). NOT the same source as
`epicentr_food_ua` -- that spider reads the Zakaz.ua white-label platform's
FOOD-only storefront (epicentr.zakaz.ua); this spider reads Epicentr K's own
domain, which carries the general-merchandise catalog (zero food overlap:
the Zakaz.ua "epicentr" chain has exactly one FOOD-format store, per
2026-09-06 stores-api.zakaz.ua check).

Nuxt 2 SSR app. Listing pages embed the full product list for the category
in a `window.__NUXT__` payload, but it is wrapped in an IIFE with
single/double-letter argument names (Nuxt's payload de-duplication
minifier) -- not parseable as JSON via regex. Playwright is required to
execute the page and read `window.__NUXT__` back out as a real object
(`page.evaluate`); a plain curl_cffi GET (200, no WAF) gets the same
unparseable script text, so Playwright is used only to deobfuscate, not to
beat a block. `data[0].listingProducts` is a flat array of
{id/productId, name, price, url, categoryId, ...} -- price is already in
whole UAH (verified: HP laptop id 004993916 priced 33999, a plausible
~$800 UAH laptop price, not a minor-unit value).

Categories crawled (footer nav sample, no site-wide category tree found
in the time budget): avtoshiny (tires), keramicheskaya-plitka-i-keramogranit
(tiles/construction materials), konstruktory-lego (toys), noutbuki
(laptops), sportivnye-tovary (sport goods). Single page per category (no
pagination followed) -- MVP breadth pass, not a full-catalog walk.
"""

import json
import logging

import scrapy
from scrapy_playwright.page import PageMethod

logger = logging.getLogger(__name__)

_CATEGORIES = [
    "avtoshiny",
    "keramicheskaya-plitka-i-keramogranit",
    "konstruktory-lego",
    "noutbuki",
    "sportivnye-tovary",
]

_EVAL_JS = "() => JSON.stringify(window.__NUXT__)"


class EpicentrkUaSpider(scrapy.Spider):
    name = "epicentrk_ua"
    allowed_domains = ["epicentrk.ua"]
    currency = "UAH"
    language = "uk"

    custom_settings = {
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1,
    }

    async def start(self):
        for slug in _CATEGORIES:
            url = f"https://epicentrk.ua/ua/shop/{slug}/"
            yield scrapy.Request(
                url,
                callback=self.parse,
                meta={
                    "playwright": True,
                    "playwright_page_goto_kwargs": {"wait_until": "domcontentloaded"},
                    "playwright_page_methods": [
                        PageMethod("wait_for_timeout", 3000),
                        PageMethod("evaluate", _EVAL_JS),
                    ],
                    "slug": slug,
                },
                dont_filter=True,
            )

    def parse(self, response):
        slug = response.meta["slug"]
        methods = response.meta["playwright_page_methods"]
        raw = methods[1].result
        if not raw:
            logger.warning(f"epicentrk_ua: empty __NUXT__ eval on {slug}")
            return
        try:
            data = json.loads(raw)
            listing = data["data"][0].get("listingProducts", [])
        except (KeyError, IndexError, ValueError) as exc:
            logger.warning(f"epicentrk_ua: could not walk __NUXT__ on {slug}: {exc}")
            return

        logger.info(f"epicentrk_ua slug={slug} count={len(listing)}")
        for p in listing:
            item = self._item(p, slug)
            if item:
                yield item

    def _item(self, p: dict, slug: str):
        name = p.get("name")
        url = p.get("url")
        product_id = p.get("id") or p.get("productId")
        price = p.get("price")
        if not (name and url and product_id and price):
            return None
        try:
            price = float(price)
        except (TypeError, ValueError):
            return None
        if price <= 0:
            return None
        return {
            "product_id": str(product_id),
            "product_name": name.strip(),
            "category": slug,
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": url,
            "language": self.language,
        }
