"""
ECCB ECCU Fuel Price Tracker, Antigua and Barbuda —
https://www.eccb-centralbank.org/eccu-fuel-price-tracker.

The Eastern Caribbean Central Bank publishes a per-member-country fuel
price dashboard. The page itself ships no data -- a Highcharts widget
(cdn.eccb-centralbank.org/assets/js/fuel-tracker.js) POSTs back to the
same page URL with {chartId, countryId} and gets JSON back. It is a
Laravel app: the POST needs the page's CSRF token (meta[name=csrf-token])
echoed as X-CSRF-TOKEN plus the session cookie set on the GET, or it
answers 419 Page Expired.

countryId=2 is Antigua and Barbuda (confirmed from the <select id=
"chart1Country"> options). chartId=1 is the "Average Gasoline and Diesel
Prices (EC$ Per Imperial Gallon)" annual series -- confirmed response
carries startYear=2005, latestYear=2025, one {name, data:[[year, value]]}
series per fuel type. This is the long-history series (21 years); the
sibling chartId=2 is a 13-month rolling window of the same two fuels and
is redundant with the tail of chartId=1, so only chartId=1 is scraped.

Smoke-verified 2026-08-31: 42 rows (21 years x 2 fuels), single currency
XCD, 2013 diesel and 2016 diesel are null in the source and are skipped.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.eccb-centralbank.org"
PAGE_PATH = "/eccu-fuel-price-tracker"
COUNTRY_ID = 2  # Antigua and Barbuda
CHART_ID = 1  # Average Gasoline and Diesel Prices (EC$ Per Imperial Gallon)
_CSRF_RE = re.compile(r'name="csrf-token"\s+content="([^"]+)"')


class EccbFuelTrackerAgSpider(scrapy.Spider):
    name = "eccb_fuel_tracker_ag"
    allowed_domains = ["eccb-centralbank.org"]
    currency = "XCD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "COOKIES_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            f"{BASE_URL}{PAGE_PATH}",
            callback=self.parse_page,
            errback=self.errback,
        )

    def parse_page(self, response):
        m = _CSRF_RE.search(response.text)
        if not m:
            logger.error(f"{self.name}: csrf-token not found on {response.url}")
            return
        token = m.group(1)
        yield scrapy.FormRequest(
            f"{BASE_URL}{PAGE_PATH}",
            formdata={"chartId": str(CHART_ID), "countryId": str(COUNTRY_ID)},
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "X-CSRF-TOKEN": token,
                "Referer": f"{BASE_URL}{PAGE_PATH}",
                "Accept": "application/json",
            },
            callback=self.parse_chart,
            errback=self.errback,
        )

    def parse_chart(self, response):
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON response at {response.url}")
            return
        try:
            series = json.loads(data["seriesData"])
        except (KeyError, ValueError, TypeError):
            logger.warning(f"{self.name}: unexpected chart payload shape")
            return

        count = 0
        for s in series:
            fuel = (s.get("name") or "").strip()
            for year, value in s.get("data") or []:
                if value is None:
                    continue
                yield {
                    "product_id": f"eccb_fuel_ag_{fuel.lower()}_{year}",
                    "product_name": f"{fuel} (EC$ per imperial gallon, annual average)",
                    "category": "Fuel",
                    "price": str(value),
                    "currency": self.currency,
                    "available": True,
                    # DuplicationPipeline dedups on item['url']; every row
                    # would otherwise share the same tracker-page URL and
                    # all but the first would be silently dropped.
                    "url": f"{BASE_URL}{PAGE_PATH}#{fuel.lower()}-{year}",
                    "language": self.language,
                    "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
                }
                count += 1
        logger.info(f"{self.name}: emitted {count} rows")

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
