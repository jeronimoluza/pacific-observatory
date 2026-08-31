"""
Antigua Public Utilities Authority (APUA) — customer service rates page,
https://www.apua.ag/customer-service/rates/.

APUA is the sole electricity and water utility for Antigua and Barbuda.
The rates page is a WPBakery tabbed-accordion widget (div.vc_tta-panel
per utility/customer-class tab: electricity domestic/commercial, water
domestic/commercial, telephone domestic/commercial) with the tariff
schedule as plain <li> bullet lines, not a table. Telephone tabs carry no
priced bullet lines (prose only) and are skipped.

Each tab's <li> list is nested (a summary "Consumption Charge: <sub-items>"
li wraps the same sub-items as separate child <li>s); only leaf <li>s
(no nested <ul>) are emitted, else every sub-rate would double-count under
its wrapping bullet.

Smoke-verified 2026-08-31: 17 leaf rate lines across 4 priced tabs
(electricity-dom 4, electricity-com 6, water-dom 4, water-com 3), all
prices in EC$ (XCD), single page therefore a flat row count run to run --
expected for a static tariff schedule, not a pagination failure.
"""

import hashlib
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.apua.ag"
PAGE_PATH = "/customer-service/rates/"
_PRICE_RE = re.compile(r"[$@]\s*([\d,]+\.\d{2})")


class ApuaRatesAgSpider(scrapy.Spider):
    name = "apua_rates_ag"
    allowed_domains = ["apua.ag"]
    start_urls = [f"{BASE_URL}{PAGE_PATH}"]
    currency = "XCD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
    }

    def parse(self, response):
        count = 0
        for panel in response.css("div.vc_tta-panel"):
            title = panel.css(".vc_tta-title-text::text").get(default="").strip()
            if not title:
                continue
            body = panel.css(".vc_tta-panel-body")
            # Leaf <li>s only: those with no nested <ul> (the wrapping
            # summary <li> repeats its children's text and would double-count).
            leaf_lis = [li for li in body.css("li") if not li.css("ul")]
            for li in leaf_lis:
                text = " ".join(
                    t.strip() for t in li.css("::text").getall() if t.strip()
                )
                m = _PRICE_RE.search(text)
                if not m:
                    continue
                price = m.group(1).replace(",", "")
                pid = hashlib.md5(f"{title}|{text}".encode()).hexdigest()[:12]
                yield {
                    "product_id": f"apua_{pid}",
                    "product_name": text[:500],
                    "category": title,
                    "price": price,
                    "currency": self.currency,
                    "available": True,
                    # DuplicationPipeline dedups on item['url']; every row
                    # on this single-page tariff schedule would otherwise
                    # share response.url and all but the first row would be
                    # silently dropped.
                    "url": f"{response.url}#{pid}",
                    "language": self.language,
                    "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
                }
                count += 1
        logger.info(f"{self.name}: emitted {count} rows")
