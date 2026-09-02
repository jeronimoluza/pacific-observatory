"""
Bahamas Power and Light (BPL) — Monthly Fuel Charge history,
https://www.bplco.com/fuel-charge-update/.

BPL is the sole electricity utility for New Providence and the Family
Islands. Every residential/commercial bill is consumption charge + a
"fuel charge" (cents per kWh) that BPL republishes monthly, split into a
lower rate for usage under 800 kWh and a higher rate above it. The page
is a plain server-rendered HTML table listing every past Statement
Period back for years, not just the current month -- a real historical
tariff series, not a single hardcoded snapshot, and not a capped/broken
crawl (a flat page is expected for a static schedule page, per the
apua_rates_ag precedent).

Values are published in cents per kWh; divided by 100 here so `price` is
a plain BSD amount consistent with every other source's units (BSD is
pegged 1:1 to USD).

Every row on this single-page table shares response.url, so each row (one
per period x usage tier) gets a unique synthetic URL fragment
(...#<period>-lt800 / -gt800) -- the DuplicationPipeline dedups on
item['url'] and would otherwise silently drop all but the first row (see
apua_rates_ag.py).
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.bplco.com"
PAGE_PATH = "/fuel-charge-update/"
_ROW_RE = re.compile(
    r"<td[^>]*>([A-Za-z]+ \d{4})</td>\s*"
    r"<td[^>]*>([\d.]+)</td>\s*"
    r"<td[^>]*>([\d.\-]+)</td>",
)


class BplFuelChargeBsSpider(scrapy.Spider):
    name = "bpl_fuel_charge_bs"
    allowed_domains = ["bplco.com"]
    start_urls = [f"{BASE_URL}{PAGE_PATH}"]
    currency = "BSD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
    }

    def parse(self, response):
        count = 0
        for period, lt800, gt800 in _ROW_RE.findall(response.text):
            period_key = period.strip().lower().replace(" ", "-")
            for tier_label, tier_key, raw in (
                ("Fuel Charge < 800 kWh Usage", "lt800", lt800),
                ("Fuel Charge > 800 kWh Usage", "gt800", gt800),
            ):
                try:
                    cents = float(raw)
                except ValueError:
                    continue
                if cents < 0:
                    # e.g. "-0.0" placeholder rows some months carry; not a
                    # real published rate.
                    continue
                dollars = cents / 100
                yield {
                    "product_id": f"bpl_fuel_{period_key}_{tier_key}",
                    "product_name": f"{tier_label} — {period}",
                    "category": tier_label,
                    "price": str(dollars),
                    "currency": self.currency,
                    "available": True,
                    "url": f"{response.url}#{period_key}-{tier_key}",
                    "language": self.language,
                    "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
                }
                count += 1
        logger.info(f"{self.name}: emitted {count} rows")
