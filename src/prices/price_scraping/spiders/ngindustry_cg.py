"""NG Industry (Congo-Brazzaville) -- https://ngindustry.insight.cg/en/shop.

Odoo eCommerce (Website Sale module) -- not Shopify/Woo/Presta/OpenCart. Odoo
server-renders the listing page (/shop, /shop/page/N) with standard RDFa/
microdata: each card is `itemscope itemtype="http://schema.org/Product"`,
carrying `itemprop="name"` on the title anchor and a hidden
`<span itemprop="price">`/`<span itemprop="priceCurrency">` pair inside the
`itemtype="http://schema.org/Offer"` block (the visible `oe_currency_value`
spans are locale-formatted display text, not the machine-readable value).
No JSON-LD on this theme, so the shared rows_from_jsonld/row_from_meta
helpers don't apply -- this spider reads the microdata directly off the
listing page, which already carries name+price+url, no PDP fetch needed.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE = "https://ngindustry.insight.cg"
START_URL = f"{BASE}/en/shop"
MAX_PAGES = 15

_CARD_SPLIT_RE = re.compile(r'itemtype="http://schema\.org/Product"')
_URL_RE = re.compile(r'itemprop="url"\s+href="([^"]+)"')
_NAME_RE = re.compile(r'itemprop="name"[^>]*content="([^"]+)"')
_PRICE_RE = re.compile(r'itemprop="price"[^>]*>([\d.]+)</span>')
_CURRENCY_RE = re.compile(r'itemprop="priceCurrency"[^>]*>([A-Z]{3})</span>')


class NgindustryCgSpider(scrapy.Spider):
    name = "ngindustry_cg"
    allowed_domains = ["ngindustry.insight.cg"]
    currency = "XAF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "ROBOTSTXT_OBEY": False,
    }

    async def start(self):
        yield scrapy.Request(START_URL, callback=self.parse_listing, meta={"page": 1})

    def parse_listing(self, response):
        blocks = _CARD_SPLIT_RE.split(response.text)[1:]
        logger.info(f"ngindustry_cg: {response.url} cards={len(blocks)}")
        for block in blocks:
            item = self._item(block, response.url)
            if item:
                yield item
        page = response.meta["page"]
        if blocks and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{BASE}/en/shop/page/{nxt}",
                callback=self.parse_listing,
                meta={"page": nxt},
            )

    def _item(self, block: str, listing_url: str):
        um = _URL_RE.search(block)
        nm = _NAME_RE.search(block)
        pm = _PRICE_RE.search(block)
        cm = _CURRENCY_RE.search(block)
        if not (um and nm and pm):
            return None
        url = um.group(1)
        if url.startswith("/"):
            url = BASE + url
        price = pm.group(1)
        if not price or float(price) <= 0:
            return None
        return {
            "product_name": nm.group(1).strip()[:500],
            "price": price,
            "currency": cm.group(1) if cm else self.currency,
            "available": True,
            "url": url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
