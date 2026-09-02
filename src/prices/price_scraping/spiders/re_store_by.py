"""Spider for Re-Store (Belarus) -- https://re-store.by/.

"Ресторация" (re-store.by, legal entity OOO "Vodny Mir", UNP 190756996) is a
Minsk online delicatessen/specialty-food delivery store -- distinct company
from the other two Belarusian grocers already onboarded this wave
(foodstore_by = food-store.by / 1C-Bitrix "item-title" theme; green_dostavka_by
= green-dostavka.by / sitemap+JSON-LD walk). `curl_cffi impersonate=chrome124`
clears cleanly with HTTP 200, no anti-bot layer observed.

Server-rendered Bitrix storefront. 215 leaf `/catalog/<slug>/` categories
reachable from the homepage nav. Each category listing card carries a
structured `data-analytics='{"id": "...", "name": "...", "category": "...",
"price": ...}'` JSON attribute (a GA-style ecommerce tracking blob) -- far
more reliable than parsing the visible price markup, which splits the
integer/decimal parts across separate <strong>/<small> tags with no
adjoining currency text anywhere in the DOM.

Currency: the tracking blob's own "currency" field is a stale "RUB" stub
(confirmed on a cold PDP re-fetch: price 24.30 for a 150ml soy sauce bottle
is priced consistently with BYN -- countries.yaml's declared currency for
Belarus -- and would be implausible as 24.30 RUB, ~$0.25). No BYN literal
is rendered anywhere on the page (no currency symbol/text at all), so the
spider hardcodes BYN at the class level per Phase 5A guidance rather than
trust the blob's stray field.

Pagination confirmed real via `?PAGEN_1=N`: page 1 of /catalog/bakaleya/
and page 2 return disjoint product id sets (verified cold, 2026-09-01).

Known edge case: the data-analytics attribute is single-quote-delimited; a
product name containing a literal apostrophe would prematurely terminate
the regex match and drop that one card. Rare in the observed sample and
accepted as a minor loss rather than a full HTML-attribute parser.
"""

import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://re-store.by"
_CATEGORY_HREF_RE = re.compile(r'href="(/catalog/[a-zA-Z0-9_\-]+/)"')
_CARD_RE = re.compile(r"data-analytics='(\{[^']*\})'")
MAX_PAGES = 40


class ReStoreBySpider(scrapy.Spider):
    name = "re_store_by"
    allowed_domains = ["re-store.by"]
    currency = "BYN"
    language = "ru"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_categories: set[str] = set()
        # The synthetic "<category-url>#<product_id>" url below is needed
        # because DuplicationPipeline dedups on item["url"] and the real site
        # serves every product from one path. That fix has a side effect: a
        # product listed in two category views (e.g. the homepage and
        # /catalog/f_hits/) emits twice, since its two synthetic urls differ.
        # Measured 2026-09-01: 18 products duplicated, 24 extra rows of 123.
        # product_id is the true identity here, so dedup on it directly.
        self.seen_product_ids: set[str] = set()

    async def start(self):
        yield scrapy.Request(
            f"{_BASE}/", callback=self.parse_category, meta={"page": 1}
        )

    def _new_category_requests(self, response):
        for path in _CATEGORY_HREF_RE.findall(response.text):
            if path in self.seen_categories:
                continue
            self.seen_categories.add(path)
            yield scrapy.Request(
                urljoin(_BASE, path),
                callback=self.parse_category,
                meta={"page": 1, "cat_url": urljoin(_BASE, path)},
            )

    def parse_category(self, response):
        yield from self._new_category_requests(response)

        page = response.meta["page"]
        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for blob in _CARD_RE.findall(response.text):
            try:
                data = json.loads(blob)
            except ValueError:
                continue
            product_id = data.get("id")
            name = data.get("name")
            price = data.get("price")
            if not product_id or not name or price is None:
                continue
            try:
                price_val = float(price)
            except (TypeError, ValueError):
                continue
            if price_val <= 0:
                continue
            if str(product_id) in self.seen_product_ids:
                continue
            self.seen_product_ids.add(str(product_id))
            n += 1
            yield {
                "product_id": str(product_id),
                "product_name": str(name).strip()[:500],
                "category": data.get("category"),
                "price": str(price_val),
                "currency": self.currency,
                "available": True,
                "url": f"{response.url.split('?')[0]}#{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"{self.name}: {response.url} page={page} items={n}")

        cat_url = response.meta.get("cat_url", response.url.split("?")[0])
        if n and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{cat_url}?PAGEN_1={nxt}",
                callback=self.parse_category,
                meta={"page": nxt, "cat_url": cat_url},
            )
