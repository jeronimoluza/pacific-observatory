"""Busiquip (Eswatini) -- https://busiquip.com/. Not Zoho Commerce (an
earlier automated fingerprint pass matched "zoho" against an embedded Zoho
SalesIQ chat-widget script, a false positive); this is a bespoke
React/Vite SPA for a printer/toner reseller. The homepage never calls a
catalog API -- the full 67-SKU toner catalog is a plain JS array literal
baked into a static asset bundle at build time
(/assets/tonerProducts-<hash>.js), so this spider fetches that one file and
regex-extracts each product object, no HTML parsing or pagination involved.

Currency: SZL confirmed from a PDP's JSON-LD priceCurrency (e.g.
/toners/tnp76). Eswatini-facing (Manzini/Mbabane/Nhlangano/Siteki city pages
elsewhere on the site).

Page family: neither listing nor PDP -- a static JS data bundle. Note for
the archive side: this asset's filename hash changes on every rebuild, so a
Common Crawl/Wayback snapshot's exact URL will not match a later live
fetch; there is no stable archive path for this source.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy

BUNDLE_URL = "https://busiquip.com/assets/tonerProducts-DAO6_AGr.js"
_ITEM_RE = re.compile(
    r'id:"(?P<id>[^"]+)",sku:"(?P<sku>[^"]+)",name:"(?P<name>[^"]+)",'
    r'brand:"[^"]*",category:"(?P<category>[^"]*)",color:"[^"]*",'
    r"price:(?P<price>[0-9.]+)"
)


class BusiquipSzSpider(scrapy.Spider):
    name = "busiquip_sz"
    allowed_domains = ["busiquip.com"]
    currency = "SZL"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
    }

    async def start(self):
        yield scrapy.Request(BUNDLE_URL, callback=self.parse_bundle)

    def parse_bundle(self, response):
        for m in _ITEM_RE.finditer(response.text):
            price = m.group("price")
            try:
                if float(price) == 0:
                    continue
            except (TypeError, ValueError):
                continue
            yield {
                "product_id": m.group("sku"),
                "product_name": m.group("name")[:500],
                "category": m.group("category") or None,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": f"https://busiquip.com/toners/{m.group('sku').lower()}",
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
