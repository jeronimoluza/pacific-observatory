"""
Digicel Antigua & Barbuda — https://www.digicelgroup.com/ag/en/.

The site is a Next.js App Router build: plan cards are NOT in a JSON API,
they are React Server Component "flight" payloads inlined directly in the
initial HTML response as a sequence of

    self.__next_f.push([1, "<JSON-escaped string chunk>"])

script tags (no JS execution needed — curl_cffi's raw response body already
contains them). Concatenating and JSON-decoding every chunk's string
argument reassembles one long serialized-flight text blob containing the
page's full component tree, including every `PlanItemRecord` object:

    {"__typename":"PlanItemRecord","plan":{"id":..., "slug":...,
     "name":"30 Day Prime Ultra Plan",
     "productCategory":{"slug":"prepaid","name":"Prepaid",...},
     ..., "originalPriceValue":132, ...}}

Locality/currency proof: the SAME rendered HTML (not just the flight JSON)
shows the price span as literal text "XCD\xa0132.00" next to the "132"
plan-price banner text — confirmed by grepping the raw response body, not
inferred. This is a genuine Antigua-market (/ag/en) storefront pricing in
XCD, not a USD-priced diaspora shop.

Three category pages were probed and confirmed to carry priced plans:
prepaid (11 plans), postpaid (12 plans), home internet (3 plans) — 26
distinct plan objects total. `/ag/en/bundles/internet-tv` returned zero
matches on this probe and was dropped rather than guessed at further.

Plan ids are the Dato/GraphQL-CMS record ids (stable across requests).
Since all three pages are visited in one spider, `seen_ids` dedupes the
(rare) case of the same plan surfacing on more than one page.
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


class DigicelAgSpider(scrapy.Spider):
    name = "digicel_ag"
    allowed_domains = ["digicelgroup.com"]
    start_urls = [
        f"{BASE_URL}/ag/en/mobile/prepaid",
        f"{BASE_URL}/ag/en/mobile/postpaid",
        f"{BASE_URL}/ag/en/home-and-entertainment/internet",
    ]
    currency = "XCD"
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
            if plan_id in self.seen_ids:
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
