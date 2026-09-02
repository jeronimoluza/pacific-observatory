"""MTN Sudan prepaid internet bundle tariffs (tariff source, plain HTML).

https://www.mtn.sd/bundle-type/20 is a Next.js page that server-renders its
bundle cards -- unlike Zain's SharePoint page, a plain curl_cffi GET returns
the full HTML with every card's data volume, price and validity already in
the response body. Each card is a
`<div class="bg-white rounded-2xl shadow-xl ...">` block containing an
`<h3>` bundle name and "Resources / Recourses with Bonus / Price Vat Inc /
Validity" list lines.

Trap: the "Price Vat Inc" label is inconsistently formatted across cards --
most are "Price Vat Inc: 1800" but some render "Price Vat Inc:15000" (no
space) or "Price Vat Inc88000" (colon dropped entirely). A regex requiring
`: ` would silently drop 3 of 17 cards; `Price Vat Inc\\s*:?\\s*(\\d+)`
catches all three variants.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

URL = "https://www.mtn.sd/bundle-type/20"
CARD_SPLIT = "bg-white rounded-2xl shadow-xl"
NAME_RE = re.compile(r'<h3 class="text-xl font-bold text-gray-900[^>]*>([^<]+)</h3>')
PRICE_RE = re.compile(r"Price Vat Inc\s*:?\s*(\d+)")
VALIDITY_RE = re.compile(r"Validity:\s*([^<]+)</span>")


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.strip().lower()).strip("-")


class MtnPrepaidInternetSdSpider(scrapy.Spider):
    name = "mtn_prepaid_internet_sd"
    allowed_domains = ["mtn.sd"]
    currency = "SDG"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2,
    }

    async def start(self):
        yield scrapy.Request(
            URL, callback=self.parse, meta={"impersonate": "chrome124"}
        )

    def parse(self, response):
        cards = response.text.split(CARD_SPLIT)[1:]
        yielded = 0
        seen_ids = set()
        for card in cards:
            name_m = NAME_RE.search(card)
            price_m = PRICE_RE.search(card)
            if not (name_m and price_m):
                continue
            name = name_m.group(1).strip()
            price = price_m.group(1)
            validity_m = VALIDITY_RE.search(card)
            validity = validity_m.group(1).strip() if validity_m else ""

            # Bundles that differ only in validity (e.g. 5GB/24H vs 5GB/30D)
            # are distinct products at distinct prices; folding validity into
            # the id stops the second one colliding away into seen_ids.
            product_id = slugify(f"{name}-{validity}" if validity else name)
            if product_id in seen_ids:
                continue
            seen_ids.add(product_id)

            yield {
                "product_id": product_id,
                "product_name": (
                    f"{name} Prepaid Internet Bundle"
                    + (f" ({validity})" if validity else "")
                )[:500],
                "category": "Prepaid Internet",
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": f"{response.url}#{product_id}",
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            yielded += 1
        logger.info(
            f"mtn_prepaid_internet_sd: yielded {yielded} bundles (validity samples logged)"
        )
