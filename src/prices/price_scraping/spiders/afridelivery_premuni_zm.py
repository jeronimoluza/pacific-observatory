"""Premuni Stores on AfriDelivery (Zambia) — https://afridelivery.app/

Premuni Stores is a named specialty grocer (South-Asian import groceries:
Parle biscuits, Wagh Bakri tea, spices, pulses, papad, flour, condiments)
operating two Lusaka branches on the AfriDelivery multi-vendor delivery
platform (backend host api.afrideliverymall.com, shared with the "250taxi"
white-label courier template). AfriDelivery itself lists 9 distinct
grocery/food vendors across ~109 Lusaka delivery zones (butcheries,
a fishmonger, a produce store, etc.) — Premuni Stores is scraped here as
its own first-party merchant per onboarding rule 14 ("a named supermarket
behind a delivery app is a supermarket"), not as a blended AfriDelivery
aggregate, because the vendor set is not homogeneous enough to carry one
honest channel label.

No per-product PDP exists — the platform serves an AJAX HTML-fragment
"menu" for each vendor id (task=menu). Confirmed live 2026-09-01:
GET https://api.afrideliverymall.com/?api=restaurants_2026b&task=menu&id=527...
-> 200, 263 items, ALL priced (real ZMW magnitudes, e.g. 'Parle Hide & Seek
247.5g' K 50.40); id=532 (a second branch, "Premuni Stores Cosmopolitan
Mall") -> 200, 262 items, ALL priced (e.g. 'CHEESE CHEDDAR 250g' K 90.40).
Two branches use disjoint item-id ranges (40xxx vs 93xxx) so no product_id
collision. Category comes from the vendor's own menu section headers
(Biscuits, Spices, Tea/Coffee, Pulses, Papad, Flour, Dairy, Frozen,
Condiments, Nuts, Sweets, Confectionery, Snacks, Starches) — a genuine
breadcrumb-equivalent, not invented.

Zone/vendor discovery: queried task=list across all ~109 Lusaka delivery
zones with stype21=groceries; only 9 distinct vendor ids surfaced in
total (Premuni Stores x2, Zambeef x2, Eliado Meat Supplies, Yalelo, The
Paches Store, Dew Fresh, Trefo Zambia) — a small, finite, already-fully-
enumerated universe, hence the two branch ids are hardcoded below rather
than re-discovered per run.

Locality: AfriDelivery operates in Lusaka/Kitwe/Ndola/Solwezi, Zambia
only; prices render with a "K" (Kwacha) prefix client-side — set
explicitly to ZMW at the spider level, matching countries.yaml.

Rule 9 (DuplicationPipeline dedups on item['url']): there is no
per-product URL on this platform, so a synthetic URL is built as the
menu endpoint plus a '#<vendor>-<item_id>' fragment per row.
"""

import re
from datetime import datetime, timezone

import scrapy

_ZONES = ["Cairo Road", "Kabulonga", "Manda Hill", "Roma", "Northmead", "Woodlands"]
_BRANCHES = [
    ("527", "Premuni Stores"),
    ("532", "Premuni Stores"),
]
_MENU_URL = (
    "https://api.afrideliverymall.com/?api=restaurants_2026b&task=menu"
    "&id={vendor_id}&zone={zone}&type=shop&stype21=stores&user_id=0"
    "&update_level=2026june"
)

_ITEM_RE = re.compile(
    r"afri_menu_item_category_name[^>]*>\s*(?P<cat>[^<\n]+)"
    r"|add_menu_item\('(?P<id>\d+)','(?P<price>[\d.]+)','(?P<name>[^']*)','[^']*','[^']*'\);"
)


class AfrideliveryPremuniZmSpider(scrapy.Spider):
    name = "afridelivery_premuni_zm"
    allowed_domains = ["afrideliverymall.com"]
    currency = "ZMW"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
    }

    async def start(self):
        # Any live zone returns the same store-specific menu — the zone
        # only affects delivery eligibility, not the catalog — but keep a
        # fallback zone list in case a given zone 404s for a branch.
        for vendor_id, vendor_name in _BRANCHES:
            zone = _ZONES[0]
            url = _MENU_URL.format(vendor_id=vendor_id, zone=zone.replace(" ", "%20"))
            yield scrapy.Request(
                url,
                callback=self.parse_menu,
                cb_kwargs={"vendor_id": vendor_id, "vendor_name": vendor_name},
            )

    def parse_menu(self, response, vendor_id, vendor_name):
        text = response.text
        current_cat = None
        n = 0
        for m in _ITEM_RE.finditer(text):
            if m.group("cat") is not None:
                current_cat = m.group("cat").strip()
                continue
            item_id = m.group("id")
            price = m.group("price")
            name = m.group("name").strip()
            if not name or price in (None, "", "0.00", "0"):
                continue
            n += 1
            yield {
                "product_id": f"{vendor_id}_{item_id}",
                "product_name": name,
                "category": current_cat,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": f"{response.url}#{vendor_id}-{item_id}",
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        self.logger.info(
            "afridelivery_premuni_zm: vendor %s (%s) -> %d priced items",
            vendor_id,
            vendor_name,
            n,
        )
