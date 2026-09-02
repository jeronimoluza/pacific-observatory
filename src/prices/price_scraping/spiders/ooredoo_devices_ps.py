"""
Ooredoo Palestine (formerly Wataniya Mobile) device store —
https://www.ooredoo.ps/handsets/.

Server-rendered storefront (Tier 1A): the homepage itself carries the
complete device catalog as four tab panels (`#tab-<id>` divs, one per
category -- smartphones, accessories, gaming devices, tablets), each a
`.products-list` of `.products-list__item__inner` cards with a
server-rendered price and an "ILS" currency suffix already in the markup
(`<span class="products-list__item__price__curr">ILS</span>`). No AJAX,
no pagination: `/handsets/devices/<id>.html` IDs are sparse (probed 21
IDs in the 1-3000 range outside the ~27 known-good ones, all 404), and no
listing/category endpoint distinct from the homepage tabs was found in the
page nav, breadcrumbs, or the two linked JS bundles (`ods_v2_build.js`,
`ods_ie_build.js` -- no `/api/` or fetch endpoint in either). This IS the
catalog, not a curated carousel slice of a larger one: verified page 2 does
not exist and no second product set is reachable.

Re-verified live 2026-09-01: 27 distinct devices across the 4 tabs --
flagship + budget phones (Samsung Galaxy S26 Ultra 3150 ILS, iPhone 17 Pro
Max 5670 ILS down to Samsung A07 380 ILS), Apple Watches, PlayStation 5 /
Xbox / Nintendo Switch 2, an iPad, and accessories (chargers, controllers).
Each product has its own detail page with real installment/credit-card
purchase links (`/handsets/ods/purchase/...`), i.e. a genuine sellable SKU,
not a spec-sheet placeholder.

channel: electronics (phone/device retailer, not a supermarket -- does not
count toward the food-and-beverage bar). Locality: ooredoo.ps is the
Palestinian carrier's own domain, prices in ILS, West-Bank-and-Gaza mobile
network operator -- unambiguously local.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.ooredoo.ps"
START_URL = f"{BASE_URL}/handsets/"

_ID_RE = re.compile(r"/devices/(\d+)\.html")


class OoredooDevicesPsSpider(scrapy.Spider):
    name = "ooredoo_devices_ps"
    allowed_domains = ["ooredoo.ps"]
    currency = "ILS"
    language = "ar"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(START_URL, callback=self.parse_index, errback=self.errback)

    def parse_index(self, response):
        # Map each "#tab-<id>" nav link to its human-readable category label.
        tab_labels: dict[str, str] = {}
        for link in response.css("a[href^='#tab-']"):
            href = link.attrib.get("href", "")
            tab_id = href.lstrip("#")
            label = " ".join(link.css("*::text").getall()).strip()
            if tab_id and label:
                tab_labels[tab_id] = label

        seen_ids: set[str] = set()
        found = 0
        for tab in response.css("[id^='tab-']"):
            tab_id = tab.attrib.get("id", "")
            category = tab_labels.get(tab_id, tab_id)
            for card in tab.css("a.products-list__item__inner"):
                href = card.attrib.get("href", "")
                id_match = _ID_RE.search(href)
                product_id = id_match.group(1) if id_match else None
                if not product_id or product_id in seen_ids:
                    continue
                name = (card.attrib.get("title") or "").strip() or " ".join(
                    card.css(".products-list__item__title::text").getall()
                ).strip()
                price_text = " ".join(
                    card.css(".products-list__item__price::text").getall()
                ).strip()
                price_match = re.search(r"[\d,.]+", price_text)
                if not name or not price_match:
                    continue
                price = price_match.group(0).replace(",", "")
                if float(price) <= 0:
                    continue
                seen_ids.add(product_id)
                found += 1
                yield {
                    "product_id": product_id,
                    "product_name": name[:500],
                    "category": category,
                    "price": price,
                    "currency": self.currency,
                    "available": True,
                    "url": response.urljoin(href),
                    "language": self.language,
                    "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
                }
        logger.info(f"{self.name}: tabs={len(tab_labels)} yielded={found}")

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
