"""
Relon Aden (Yemen) — https://mapp.sa/relon/ ("relon aden / ريلون عدن").

A single-tenant storefront hosted on mapp.sa, a Saudi multi-tenant
store-builder SaaS (Overzaki-style — same category of platform as Zid).
Confirmed Yemen-scoped, not a Saudi listing: the storefront's own
`getCountryDataByCode?code=ye` call resolves to `prefix: 967` (Yemen's
country code), and every category/product is branded "relon aden / ريلون
عدن" (Aden). Sniffed via Playwright network capture on
https://mapp.sa/relon/Category/98044/products, then confirmed the AJAX
endpoint works standalone with plain curl_cffi + a Referer header:

    GET /relon/fetchCatProducts?limit=<N>&start=0&main_category_id=<id>&filter=

Returns `{"success", "html"}` where `html` is a raw product-card fragment
(div.productItem) parsed directly.

Pagination via `start` is UNRELIABLE — `start=0` and `start=1` return the
byte-identical page, `start=2` returns a different (non-contiguous) slice,
and `start>=3` returns empty; `limit` above the category's real size is
simply ignored rather than erroring (limit=50/100/200 for category 98044
all returned the same 22 products). So this spider does NOT paginate: one
request per category id with a generously large limit (200) already
returns everything that category has — verified by the limit-saturation
test above.

Site structure is two top-level branches: "سوبر ماركت" (Supermarket, id
98044, itself small) with four food subcategories — مشروبات/beverages
(98045), شبسات/chips (98046), مستورد/imported (98047), متنوع/misc (98048) —
plus a fifth food category outside that branch, طعام ونوديلز كوري/Korean
food and noodles (99817). All six ids are walked here. Two non-food ids
exist on the same tenant (اكسسوارات/accessories 98049, صناديق عشوائية/
mystery boxes 99795) and are deliberately EXCLUDED — this is why the source
is tagged `channel: specialty-food` (an imported-snacks/beverage corner
shop, not a full grocery supermarket — no fresh produce, meat, rice or oil
were observed) rather than `supermarket`.

Small catalog: 26 distinct products across the 6 food category ids
(some product ids repeat across categories/subcategory overlap — deduped
by product_id in this spider). Prices in the 300-2,500 range are consistent
with YER for snack-scale goods (300-2,500 SAR for a bag of chips would be
absurd) — see the YAML notes for the full currency-symbol caveat (the site
renders the generic "﷼" glyph shared by SAR/YER/QAR/OMR, not an explicit
currency code).
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://mapp.sa/relon"
# Food-relevant category ids only — accessories (98049) and mystery boxes
# (99795) are deliberately excluded, see module docstring.
CATEGORY_IDS = ["98044", "98045", "98046", "98047", "98048", "99817"]
_PRICE_RE = re.compile(r"([\d,]+)")
_PID_RE = re.compile(r"/product/(\d+)/")


class RelonAdenYeSpider(scrapy.Spider):
    name = "relon_aden_ye"
    allowed_domains = ["mapp.sa"]
    currency = "YER"
    language = "ar"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        for cat_id in CATEGORY_IDS:
            yield scrapy.Request(
                f"{BASE_URL}/fetchCatProducts?limit=200&start=0&main_category_id={cat_id}&filter=",
                callback=self.parse_category,
                errback=self.errback,
                headers={
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": f"{BASE_URL}/Category/{cat_id}/products",
                },
                meta={"cat_id": cat_id},
                dont_filter=True,
            )

    def parse_category(self, response):
        cat_id = response.meta["cat_id"]
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON from {response.url}")
            return

        html = data.get("html") or ""
        cards = scrapy.Selector(text=html).css("div.productItem") if html else []
        found = 0

        for card in cards:
            name = (card.css("div.productTitle h3::text").get() or "").strip()
            href = card.css("div.productTitle a::attr(href)").get() or ""
            price_text = card.css("div.productPrice p::text").get() or ""
            price_match = _PRICE_RE.search(price_text)
            pid_match = _PID_RE.search(href)

            if not name or not price_match or not pid_match:
                continue

            price = price_match.group(1).replace(",", "")
            if not price or float(price) <= 0:
                continue

            found += 1
            yield {
                "product_id": pid_match.group(1),
                "product_name": name[:500],
                "category": "",
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": response.urljoin(href),
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        logger.info(f"{self.name}: cat_id={cat_id} cards={len(cards)} yielded={found}")

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
