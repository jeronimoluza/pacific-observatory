"""
Imagine (Brunei) — https://imagine.com.bn/consumer/mobile/, WISH postpaid
mobile plan tariffs.

Discovery lead re-probed 2026-09-06: plain curl_cffi with a realistic
Chrome UA returns a 200, fully server-rendered Elementor/WordPress page
(no JS execution needed) with five plan cards already in the raw HTML.

Page family: listing (one tariff page, five plan cards, no pagination).

Markup: each plan lives in its own `<div class="swiper-slide" ...>` block
inside a single carousel widget. Splitting on that marker and reading the
Elementor heading widgets in document order inside each slice gives, in
order: plan name ("WISH 2"), data amount ("2"), data unit ("GB"), price
("$10"), billing period ("/month"). Confirmed identical shape across all
5 slides (WISH 2/6/15/25/50 at $10/$18/$28/$45/$75).

Currency displayed as "$" -- this is Brunei, so BND (matches
countries.yaml for brunei_darussalam; same convention as bruneida_bn and
supasave_bn in this same country directory).

All 5 cards live on one physical page -- DuplicationPipeline dedups on
item['url'] alone (see prices memory on url-dedup collapsing single-page
catalogs, same pattern as mtn_prepaid_internet_sd.yaml/
zain_prepaid_internet_sd.yaml) -- fixed here with a per-item URL fragment
(#wish-2, #wish-6, ...).

Only the postpaid "WISH" plan family is present on this page; a separate
prepaid/data-only tariff page was not probed in this pass (see /consumer/
navigation for future recovery).
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

URL = "https://imagine.com.bn/consumer/mobile/"
SLIDE_SPLIT = 'class="swiper-slide"'
HEADING_RE = re.compile(
    r'elementor-heading-title elementor-size-default">([^<]*)</h2>'
)


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.strip().lower()).strip("-")


class ImagineBnSpider(scrapy.Spider):
    name = "imagine_bn"
    allowed_domains = ["imagine.com.bn"]
    currency = "BND"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "DOWNLOAD_TIMEOUT": 30,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(URL, callback=self.parse)

    def parse(self, response):
        slides = response.text.split(SLIDE_SPLIT)[1:]
        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for slide in slides:
            headings = HEADING_RE.findall(slide[:4000])
            if len(headings) < 4:
                continue
            plan_name = headings[0].strip()
            data_amount = headings[1].strip()
            data_unit = headings[2].strip()
            price_raw = headings[3].strip()
            price_m = re.search(r"[\d.]+", price_raw)
            if not (plan_name and price_m):
                continue
            price = float(price_m.group(0))
            if price <= 0:
                continue
            n += 1
            yield {
                "product_id": slugify(plan_name),
                "product_name": f"Imagine {plan_name} ({data_amount}{data_unit}/month postpaid)",
                "category": "mobile postpaid plan",
                "price": str(price),
                "currency": self.currency,
                "available": True,
                "url": f"{URL}#{slugify(plan_name)}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"{self.name}: emitted {n} plans")
