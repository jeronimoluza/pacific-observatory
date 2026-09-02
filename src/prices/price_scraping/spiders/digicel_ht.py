"""
Digicel Haiti — https://www.digicelgroup.com/ht/en/mobile/prepaid.

Same Next.js App Router "flight payload" platform already shipped for
Digicel Antigua & Barbuda (see digicel_ag.py's docstring for the mechanism
-- plan cards are React Server Component chunks inlined as
`self.__next_f.push([1, "<JSON-escaped chunk>"])` script tags in the raw
HTML, no JS execution needed). This spider reuses the exact same
chunk-concat + regex-extract approach against the Haiti locale (/ht/en).

Locality/currency proof: the rendered HTML shows plan-price banners as
literal text "HTG\xa012.00", "HTG\xa022.50", etc. -- confirmed by grepping
the raw response body and cross-checking 10 values 1:1 against the parsed
JSON `originalPriceValue` field (12, 22.5, 35, 45, 50, 70, 90, 120, 130,
140 all matched exactly). This is a genuine Haiti-market (/ht/en)
storefront pricing in HTG, not a USD diaspora page.

Only /mobile/prepaid is scraped (44 raw plan records: DigiPaleNet [data],
DigiNet [internet-focused bundles], DigiTalk [voice+data], plus
Caribbean/international roaming add-ons). /mobile/postpaid was probed and
dropped: its five core plans (Basic Plus Hybrid, Elite Hybrid, Elite/
Platinum/Platinum Pro Postpaid) all carry the identical placeholder
`originalPriceValue: 10` -- not a real per-plan price, most likely a
"starting from" marketing teaser for credit-approval plans, not something
worth tracking as a price observation.

One prepaid record is a confirmed data defect and is dropped by slug:
slug "14-day-caribbean-plan-roaming" ("14 Day Caribbean Plan") carries
originalPriceValue=4, but the SAME plan (same 14-day Caribbean roaming
description) appears correctly on the postpaid page under slug
"14-day-caribbean-roaming" at originalPriceValue=4400 -- confirmed a
truncated/stale duplicate CMS record on the prepaid page, not a genuine
HTG 4 plan. Every other Caribbean/international roaming plan on the
prepaid page (3-day/7-day Caribbean at 1100/2200, 3-day/7-day/30-day
international at 900/1800/300) has a plausible, internally consistent
price and is kept.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.digicelgroup.com"
_CHUNK_RE = re.compile(r"self\.__next_f\.push\(\[1,\s*(\".*?\")\]\)", re.DOTALL)
_PLAN_RE = re.compile(
    r'"id":"([^"]+)","slug":"([^"]+)","name":"([^"]+)",'
    r'"productCategory":\{"slug":"([^"]+)","name":"([^"]+)"'
    r'.*?"originalPriceValue":([\d.]+)',
    re.DOTALL,
)
# Confirmed stale/duplicate CMS record -- see module docstring.
_DROP_SLUGS = {"14-day-caribbean-plan-roaming"}


class DigicelHtSpider(scrapy.Spider):
    name = "digicel_ht"
    allowed_domains = ["digicelgroup.com"]
    start_urls = [
        f"{BASE_URL}/ht/en/mobile/prepaid",
    ]
    currency = "HTG"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_ids: set[str] = set()

    def parse(self, response):
        full = []
        for chunk in _CHUNK_RE.findall(response.text):
            try:
                full.append(json.loads(chunk))
            except (json.JSONDecodeError, ValueError):
                continue
        blob = "".join(full)

        count = 0
        for plan_id, slug, name, cat_slug, cat_name, price in _PLAN_RE.findall(blob):
            if plan_id in self.seen_ids or slug in _DROP_SLUGS:
                continue
            self.seen_ids.add(plan_id)
            yield {
                "product_id": plan_id,
                "product_name": name[:500],
                "category": cat_name,
                "price": price,
                "currency": self.currency,
                "available": True,
                # DuplicationPipeline dedups on item['url']; multiple plans
                # share response.url, so the slug is appended as a fragment.
                "url": f"{response.url}#{slug}",
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            count += 1
        logger.info(f"{self.name}: emitted {count} rows from {response.url}")
