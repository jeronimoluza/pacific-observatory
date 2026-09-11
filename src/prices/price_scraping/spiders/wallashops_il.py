"""
WallaShops (Israel) — https://www.wallashops.co.il/.

"וואלה!שופס" (Walla!Shops), the shopping arm of the Walla portal --
"the biggest online shopping site in Israel: electronics, TVs, computers,
mobile phones, cameras, furniture..." per its own og:description. Each
row IS Walla's own fixed selling price (price_to_pay after any active
discount), not a cross-merchant comparison like zap_il -- confirmed by
the item payload carrying a single "collected" supplier/dropship id and
no per-competitor price list.

Endpoint shape and the one hard problem (per WAVE3_ADDENDUM): the single
`POST /ajax` observed in the network trace is a session-scoped RPC
dispatcher (`act=<action>&id=...&token=<session_token>`), not one fixed
catalogue route. `act=search` is the widget call the trace captured --
it always returns exactly 8 hits regardless of the query term (verified
live 2026-09-10: '', 'a', a nonsense string, and real Hebrew terms all
returned 8-item lists, though the SET of ids does vary by term, so it is
a real but severely capped quick-search dropdown -- not usable for
enumeration).

The real enumeration route is `act=category_items&id=<leaf_id>`, found by
reading the page's own jQuery (`if(category_id){ post({act:
'category_items', id: category_id}) }`). It fails with
`{"error":"invalid request - id"}` for the 8 TOP-level category ids
(512, 1152, 1808, 2126, 2163, 2434, 2938, 2983 -- these are lobby/landing
pages with no directly attached products) but succeeds for their LEAF
subcategory ids, returned as a full `{"_<id>_": {...}, ...}` dict per
call (150-279 items per subcategory in samples, no further paging inside
one subcategory).

Leaf subcategory ids are discovered by crawling each of the 8 top-level
`/category/<id>` pages and pairing each `.loby_section.subcat_section
.loby_title_wrapper .title` text with the `.cubes_module` element's
`data-id` that follows it in the same section (verified this pairing
against the rendered page, e.g. "סמארטפונים" (Smartphones) -> data-id
1554). Enumerability verified live 2026-09-10: walked all 8 top
categories -> 79 distinct leaf subcategory ids -> 7,277 total items with
zero id overlap across subcategories (sum of per-category counts ==
count of distinct product ids), i.e. page1/page2-equivalent disjointness
holds at the category-partition level. One of the 79 ids 500'd/errored
(itself a further-nested lobby id) and is skipped harmlessly.

The actual selling price is NOT a top-level field on `category_items`
rows (unlike the `search` endpoint's flat shape) -- it is base64-encoded
JSON in the row's `data` field, decoded here to read `price_to_pay`
(post-discount price the customer actually pays; verified against
`price_before_discount` on sampled rows). A handful of rows decode
`price_to_pay` as a non-numeric value (observed: `false`) -- skipped.

Currency ILS (all Israeli retail, no evidence of any other currency
field). PDP url pattern `/item/<id>` confirmed from the page's own JS
(`item.attr("href", "/item/" + item_data.id)`).

Site requires a real browser TLS fingerprint (plain requests 403; cleared
by the repo-wide `scrapy_impersonate` chrome120 profile in settings.py --
no per-spider override needed, verified live 2026-09-10).
"""

import base64
import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE = "https://www.wallashops.co.il"

# Discovered live 2026-09-10 from the homepage nav
# (שואבי אבק, סלולר וגאדג'טים, רהיטים, מוצרי חשמל, חשמל למטבח,
#  מיזוג ואיוורור, עולם הקפה, כלי עבודה וגינון).
TOP_CATEGORY_IDS = ["512", "1152", "1808", "2126", "2163", "2434", "2938", "2983"]

_TOKEN_RE = re.compile(r"var token = '([a-f0-9]+)'")


class WallashopsIlSpider(scrapy.Spider):
    name = "wallashops_il"
    allowed_domains = ["wallashops.co.il"]
    currency = "ILS"
    language = "he"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.5,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(f"{BASE}/", callback=self.parse_home, errback=self.errback)

    def parse_home(self, response):
        m = _TOKEN_RE.search(response.text)
        if not m:
            logger.error(f"{self.name}: could not find session token on homepage")
            return
        token = m.group(1)
        for cid in TOP_CATEGORY_IDS:
            yield scrapy.Request(
                f"{BASE}/category/{cid}",
                callback=self.parse_top_category,
                errback=self.errback,
                meta={"token": token, "top_id": cid},
            )

    def parse_top_category(self, response):
        token = response.meta["token"]
        seen = set()
        for section in response.css(".loby_section.subcat_section"):
            title = section.css(".loby_title_wrapper .title::text").get()
            sub_id = section.css(".cubes_module::attr(data-id)").get()
            if not sub_id or sub_id in seen:
                continue
            seen.add(sub_id)
            yield scrapy.FormRequest(
                f"{BASE}/ajax",
                formdata={"act": "category_items", "id": sub_id, "token": token},
                headers={"X-Requested-With": "XMLHttpRequest"},
                callback=self.parse_category_items,
                errback=self.errback,
                meta={"sub_id": sub_id, "sub_title": (title or "").strip()},
            )
        logger.info(
            f"{self.name}: category/{response.meta.get('top_id', '?')} "
            f"-> {len(seen)} leaf subcategories"
        )

    def parse_category_items(self, response):
        sub_id = response.meta["sub_id"]
        sub_title = response.meta["sub_title"]
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error(f"{self.name}: JSON decode failed for subcat {sub_id}")
            return
        if not isinstance(payload, dict):
            # e.g. a nested lobby id echoing {"error": "invalid request - id"}
            logger.warning(f"{self.name}: subcat {sub_id} returned no item dict: {payload}")
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for row in payload.values():
            item = self._item(row, sub_title, scraped_at)
            if item:
                n += 1
                yield item
        logger.info(f"{self.name}: subcat {sub_id} ({sub_title}) -> {n}/{len(payload)} items")

    def _item(self, row: dict, sub_title: str, scraped_at: str):
        if not isinstance(row, dict):
            return None
        raw_data = row.get("data")
        if not raw_data:
            return None
        try:
            decoded = json.loads(base64.b64decode(raw_data))
        except Exception:
            return None
        price = decoded.get("price_to_pay")
        if not isinstance(price, (int, float)) or price <= 0:
            return None
        name = (row.get("title") or "").strip()
        if not name:
            return None
        pid = row.get("id")
        return {
            "product_id": str(pid),
            "product_name": name[:500],
            "category": sub_title or None,
            "price": str(price),
            "currency": self.currency,
            "available": True,
            "url": f"{BASE}/item/{pid}",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }

    def errback(self, failure):
        logger.error(f"{self.name} request failed: {failure.request.url} — {failure.value!r}")
