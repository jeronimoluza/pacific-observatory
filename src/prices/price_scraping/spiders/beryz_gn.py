"""
Beryz (Guinea) -- https://www.beryz.com/fr/alimentation.

Next.js SPA; /fr/catalogue renders zero products server-side (confirmed
2026-08-31, matches prior probing). BUT /fr/alimentation carries a small
set of real named food products with dual retail/wholesale GNF pricing
and vendor + region tags, hardcoded directly into the React Server
Component payload (self.__next_f.push(...) chunks) rather than fetched
from an API -- there is no live catalogue endpoint to page through, this
is the whole set (6 items, one per COICOP-relevant food category: huiles,
céréales, épices, poisson, légumes, boissons).

Each self.__next_f.push([1, "<json-string>"]) chunk is itself a JSON
string literal; concatenating the json.loads()-decoded chunks recovers
the RSC tree as one text blob, from which the 5 parallel field sequences
(category badge, product name, vendor+region, retail price, wholesale
price) are pulled by position -- verified aligned 6-for-6 across all
five patterns, in document order, even though one product's block
(Soumbara artisanal) is chunked differently in the RSC stream than the
other five (numbered top-level array entries instead of one nested
array), which broke an initial single combined regex.

Retail price is the analytical_role: retailer_sku row; wholesale is
emitted as a second row per product (product_id suffixed `_gros`) since
it is a distinct, genuinely different price point for the same item, not
noise -- mirrors the _prestashop_base "remise" payment-variant pattern
used for Sakanal/Diarle.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

URL = "https://www.beryz.com/fr/alimentation"

_CHUNK_RE = re.compile(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', re.S)
_NAME_RE = re.compile(
    r'"fontSize":14,"fontWeight":700,"color":"#222","marginTop":12},"children":"([^"]+)"'
)
_VENDOR_RE = re.compile(
    r'"fontSize":12,"color":"#9D9D9D","marginTop":4},"children":"([^"]+)"'
)
_RETAIL_RE = re.compile(
    r'"fontSize":15,"fontWeight":800,"color":"#F5C200","marginTop":8},"children":"([^"]+)"'
)
_WHOLESALE_RE = re.compile(
    r'"fontSize":12,"color":"#9D9D9D"},"children":"([^"]+\(gros\))"'
)
_CATEGORY_RE = re.compile(
    r'"borderRadius":"var\(--radius-full\)"},"children":"([^"]+)"'
)
_PRICE_RE = re.compile(r"([\d\s]+)\s*GNF/([a-zà-ÿ]+)")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text):
    return _SLUG_RE.sub("-", text.lower()).strip("-")


class BeryzGnSpider(scrapy.Spider):
    name = "beryz_gn"
    allowed_domains = ["beryz.com"]
    currency = "GNF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(URL, callback=self.parse, errback=self.errback)

    def parse(self, response):
        full = ""
        for chunk in _CHUNK_RE.findall(response.text):
            try:
                full += json.loads(f'"{chunk}"')
            except Exception:
                continue

        names = _NAME_RE.findall(full)
        vendors = _VENDOR_RE.findall(full)
        retail = _RETAIL_RE.findall(full)
        wholesale = _WHOLESALE_RE.findall(full)
        categories = _CATEGORY_RE.findall(full)

        n = min(len(names), len(vendors), len(retail), len(wholesale), len(categories))
        if n == 0 or not (len(names) == len(vendors) == len(retail) == len(wholesale)):
            logger.error(
                f"{self.name}: field-count mismatch "
                f"names={len(names)} vendors={len(vendors)} retail={len(retail)} "
                f"wholesale={len(wholesale)} categories={len(categories)} -- page structure changed"
            )

        found = 0
        for i in range(n):
            name, vendor, category = names[i], vendors[i], categories[i]
            product_id = _slugify(name)

            retail_match = _PRICE_RE.search(retail[i])
            if retail_match:
                found += 1
                yield self._row(
                    product_id, name, category, vendor, retail_match, gros=False
                )

            wholesale_match = _PRICE_RE.search(wholesale[i])
            if wholesale_match:
                found += 1
                yield self._row(
                    f"{product_id}_gros",
                    name,
                    category,
                    vendor,
                    wholesale_match,
                    gros=True,
                )

        logger.info(f"{self.name}: {response.url} products={n} rows_yielded={found}")

    def _row(self, product_id, name, category, vendor, match, gros):
        amount = match.group(1).replace(" ", "").replace("\xa0", "")
        unit = match.group(2)
        suffix = " (gros)" if gros else ""
        return {
            "product_id": product_id,
            "product_name": f"{name} / {unit}{suffix} — {vendor}"[:500],
            "category": category,
            "price": amount,
            "currency": self.currency,
            "available": True,
            "url": f"{URL}#{product_id}",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
