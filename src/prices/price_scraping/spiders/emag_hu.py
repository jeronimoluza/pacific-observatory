"""
Spider for eMAG Hungary — https://www.emag.hu/.

Hungarian storefront of the same eMAG commerce platform already onboarded
for Romania (`emag_ro.py`, eca/central_europe/romania) — this spider is a
near-verbatim port, not new work, generalized to any eMAG TLD by swapping
the base domain, category slugs, and currency/locale.

The homepage and top-level department pages (`/<dept>/d`) are client-
hydrated shells with no product data; sub-department hub pages
(`/<subdept>/sd`, discovered via robots.txt's sub-department-pages sitemap)
link out to the real server-rendered category listing pages
(`/<category-slug>/c`). Re-verified live 2026-08-17:
`/okosorak/c` (smartwatches) -> 200, 60 `data-product-id` cards/page;
`/okosorak/p2/c` -> 60 more cards, zero product-id overlap with page 1.

Unlike RO's HTML-entity-encoded price text, each HU card carries a clean
HTML-escaped JSON blob in its `data-product="{&quot;...&quot;}"` attribute
(on the add-to-favorites button) with `price` as a plain integer (HUF has
no decimal subunit) and `currency`: `"HUF"` directly — no thousands-
separator parsing needed.
"""

import html
import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.emag.hu"
_CATEGORY_SLUGS = [
    "okosorak",
    "okos-otthon",
    "aktivitasmerok-1",
    "vasalok-gozallomasok",
    "kavefozok",
    "goztisztitok-elektromos-felmosok",
    "varrogepek",
    "kotyogos-kavefozok",
]
MAX_PAGES = 15

_CARD_SPLIT_RE = re.compile(r'class="card-item card-standard')
_PRODID_RE = re.compile(r'data-product-id="(\d+)"')
_NAME_RE = re.compile(r'data-name="([^"]+)"')
_URL_RE = re.compile(r'data-url="([^"]+)"')
_CATEGORY_RE = re.compile(r'data-category-name="([^"]+)"')
_DATAPRODUCT_RE = re.compile(r'data-product="([^"]+)"')
_AVAIL_RE = re.compile(r'data-availability-id="(\d+)"')


class EmagHuSpider(scrapy.Spider):
    name = "emag_hu"
    allowed_domains = ["emag.hu"]
    language = "hu"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        for slug in _CATEGORY_SLUGS:
            yield scrapy.Request(
                f"{_BASE}/{slug}/c",
                callback=self.parse_category,
                meta={"slug": slug, "page": 1},
            )

    def parse_category(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]

        html_text = response.text
        starts = [m.start() for m in _CARD_SPLIT_RE.finditer(html_text)]
        starts.append(len(html_text))

        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for i in range(len(starts) - 1):
            card = html_text[starts[i] : starts[i + 1]]
            prodid_m = _PRODID_RE.search(card)
            name_m = _NAME_RE.search(card)
            url_m = _URL_RE.search(card)
            dp_m = _DATAPRODUCT_RE.search(card)
            if not (prodid_m and name_m and url_m and dp_m):
                continue
            try:
                dp = json.loads(html.unescape(dp_m.group(1)))
            except ValueError:
                continue
            price = dp.get("price")
            currency = dp.get("currency")
            if price is None or not currency:
                continue
            cat_m = _CATEGORY_RE.search(card)
            avail_m = _AVAIL_RE.search(card)
            n += 1
            yield {
                "product_id": prodid_m.group(1),
                "product_name": html.unescape(name_m.group(1)).strip()[:500],
                "category": cat_m.group(1) if cat_m else slug,
                "price": str(price),
                "currency": currency,
                "available": avail_m.group(1) != "0" if avail_m else True,
                "url": url_m.group(1),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"{self.name}: {slug} page={page} cards={n}")

        if n and page < MAX_PAGES:
            yield scrapy.Request(
                f"{_BASE}/{slug}/p{page + 1}/c",
                callback=self.parse_category,
                meta={"slug": slug, "page": page + 1},
            )
