"""
Areeba Guinée (formerly MTN Guinée) mobile internet passes --
https://areeba.gn/pass-internet/.

Server-rendered HTML table (validity / old volume / bonus / new volume /
price), 17 rows spanning 24H/48H/Semaine/Mois validity tiers, all in GNF.
Narrow single-service tariff source (telco data plans), so the spider
yields one row per pack rather than a wide product catalog.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

URL = "https://areeba.gn/pass-internet/"
_PRICE_RE = re.compile(r"([\d\s]+)\s*GNF")


class AreebaGnSpider(scrapy.Spider):
    name = "areeba_gn"
    allowed_domains = ["areeba.gn"]
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
        found = 0
        for row in response.css("table tbody tr"):
            validity = (row.css("th::text").get() or "").strip()
            tds = [t.strip() for t in row.css("td::text").getall()]
            if len(tds) < 4 or not validity:
                continue
            new_volume, price_raw = tds[2], tds[3]
            match = _PRICE_RE.search(price_raw)
            if not match:
                continue
            amount = match.group(1).replace(" ", "").replace("\xa0", "")
            if not amount or float(amount) == 0:
                continue

            plan_name = f"Pass Internet {new_volume} / {validity}"
            product_id = f"pass-internet-{validity}-{new_volume}".lower()
            product_id = re.sub(r"[^a-z0-9]+", "-", product_id).strip("-")
            found += 1
            yield {
                "product_id": product_id,
                "product_name": plan_name[:500],
                "category": "pass-internet",
                "price": amount,
                "currency": self.currency,
                "available": True,
                "url": f"{URL}#{product_id}",
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        logger.info(f"{self.name}: {response.url} yielded={found}")

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
