"""
DoorStep (Belize) -- https://doorstepbelize.com/ (online grocery delivery,
Belmopan-only beta launch, per the homepage: "BELMOPAN city only (BEta
launch)").

The front page 403s under both plain curl and curl_cffi chrome120/chrome124/
safari17_0 with a JS "Checking your browser..." interstitial served by
Hostinger's edge ("server: hcdn"), but a real Playwright browser clears it
in ~6s -- this is a content-level JS challenge, not a hard WAF (per Phase 3
rule: curl_cffi AND Playwright both failing is the actual stop condition;
here only curl_cffi failed). Network trace of the cleared page found the
backing catalogue on a separate Hostinger e-commerce API origin that has NO
challenge at all:

    https://api-ecommerce.hostinger.com/store/<store_id>/products

Single unauthenticated GET returns the full catalogue (204 SKUs, no
pagination parameter accepted -- passing `page=` 400s with "property page
should not exist"). Confirmed live 2026-09-01: real grocery/household mix
(Flavora seasonings, Kraft condiments, DAK canned meats, Takis/Cheetos,
Coca-Cola family, bread, rice, ice, plus diapers/pads/cleaning supplies/
condoms) -- roughly half food, half household/pharmacy, small-format
(204 SKUs total) single-location delivery catalogue. Channel: `convenience`
(small-format, limited SKU count), not `supermarket` -- this is a beta
delivery app for one city, not a chain.

Currency: API returns an explicit nested `currency_code: "bzd"` object per
price (with `decimal_digits: 2`) -- prices are BZD in MINOR UNITS (cents),
confirmed against `min_amount: 200` = BZ$2.00. Divide `amount` by 100.
"""

import html
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_STORE_ID = "store_01K7G82RQFP4P73EKX07679YJF"
_API_URL = f"https://api-ecommerce.hostinger.com/store/{_STORE_ID}/products"


class DoorstepBzSpider(scrapy.Spider):
    name = "doorstep_bz"
    allowed_domains = ["api-ecommerce.hostinger.com", "doorstepbelize.com"]
    currency = "BZD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(_API_URL, callback=self.parse_products)

    def parse_products(self, response):
        try:
            payload = response.json()
        except ValueError:
            logger.warning("doorstep_bz: non-JSON response at %s", response.url)
            return
        products = payload.get("products") or []
        logger.info("doorstep_bz: %s products", len(products))
        for p in products:
            item = self._item(p)
            if item:
                yield item

    def _item(self, p: dict):
        variants = p.get("variants") or []
        if not variants:
            return None
        variant = variants[0]
        prices = variant.get("prices") or []
        if not prices:
            return None
        price_entry = prices[0]
        amount = price_entry.get("amount")
        if amount is None:
            return None
        currency_info = price_entry.get("currency") or {}
        decimals = currency_info.get("decimal_digits")
        if decimals is None:
            decimals = 2
        value = amount / (10**decimals)
        currency_code = (
            price_entry.get("currency_code")
            or currency_info.get("code")
            or self.currency
        ).upper()

        name = html.unescape(str(p.get("title") or "")).strip()
        prev = None
        while prev != name:
            prev = name
            name = html.unescape(name)
        name = re.sub(r"\s+", " ", name).strip()
        if not name:
            return None

        slug = p.get("url_handle") or p.get("slug") or p.get("id")
        return {
            "product_id": str(variant.get("sku") or p.get("id")),
            "product_name": name[:500],
            "category": None,
            "price": str(value),
            "currency": currency_code,
            "available": bool(p.get("is_available", True))
            and bool(variant.get("is_available", True)),
            "url": f"https://doorstepbelize.com/products/{slug}" if slug else "",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
