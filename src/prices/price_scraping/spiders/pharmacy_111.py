"""
Spider for 111 Pharmacy / 1药网 (China) - https://m.111.com.cn/

Listing-first crawl over the mobile site's leaf category pages. Each
/categories/<id> page server-renders ten product cards carrying the item
id, the product name and the live price, so no product-page fetch is
needed.

REPAIRED 2026-08-18. The previous CrawlSpider was pinned at ~96 products on
every run since March 2026 (112 runs, historical max 98). It started from
the mobile homepage and followed links, but that homepage exposes only 22
item links and NO category links at all, so the crawl had nowhere to go.

Why the desktop site is not used: www.111.com.cn serves its category index,
but every product and category URL linked from that index returns 404 to us
(verified 2026-08-18 on /product/971851.html, /categories/953710 and
others, with and without a Referer). Only the m. host serves real content.

Why the category ids are scanned rather than crawled: the mobile category
navigation is rendered client-side and is absent from the served HTML, so a
plain-HTTP crawl finds zero /categories/ links to follow. The underlying
JSON API (gateway.fangkuaiyi.com/mobile/category/getItemSecondCategory)
requires an md5 request signature. A numeric sweep of the observed leaf-id
window is the cheapest reliable enumeration; ids outside it simply return
a short page and are skipped.

GOTCHA -- the real price is fragmented by an inline tag:
`<span class="price">¥<i>9</i>.9</span>`. A naive [¥][\\d.]+ regex therefore
skips it and matches `<span class="del_price">¥15.00</span>` instead, which
is a CONSTANT template placeholder rendered identically on every card -- it
is not a was-price. Parsing that way yields a full catalog priced at a
uniform 15.00 CNY. Always join the child text of span.price.

GOTCHA -- responses are intermittently truncated to a ~1.9KB stub with HTTP
200 and no cards. Retried in-spider; a stub is not evidence the category is
empty.

Known limitation: each leaf page renders only its FIRST ten products.
Pagination is client-side (?page=N, ?currentPage=N and ?limit=N all return
the same ten; ?pageSize=N and ?pageNum=N return HTTP 500), so per-category
depth is capped at ten until the signed API is worked out.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://m.111.com.cn/categories/{cid}"

# Observed leaf-category id window (sparse sweep 2026-08-18 found live
# categories from 1001020 to 1002220). Scanned inclusive with margin.
_CID_START = 1001000
_CID_END = 1002300

# Below this length the response is the truncated stub, not a real page.
_MIN_BODY = 20000
_MAX_STUB_RETRIES = 3

_ITEM_ID_RE = re.compile(r"/item/(\d+)\.html")


class Pharmacy111Spider(scrapy.Spider):
    name = "pharmacy_111"
    allowed_domains = ["m.111.com.cn"]
    currency = "CNY"
    language = "zh"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
        },
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
        "DOWNLOAD_DELAY": 0.1,
        "RETRY_TIMES": 3,
        # Ids outside the live window answer 500, not 404. Retrying them
        # would quadruple the sweep for no gain.
        "RETRY_HTTP_CODES": [502, 503, 504, 408, 429],
        "AUTOTHROTTLE_ENABLED": True,
    }
    IMPERSONATE_PROFILE = "chrome131"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_ids: set[str] = set()

    async def start(self):
        for cid in range(_CID_START, _CID_END + 1):
            yield self._category_request(cid, 0)

    def _category_request(self, cid, stub_retries):
        return scrapy.Request(
            _BASE.format(cid=cid),
            callback=self.parse_category,
            meta={
                "cid": cid,
                "stub_retries": stub_retries,
                "impersonate": self.IMPERSONATE_PROFILE,
            },
            dont_filter=True,
        )

    def parse_category(self, response):
        cid = response.meta["cid"]
        stub_retries = response.meta["stub_retries"]

        if len(response.text) < _MIN_BODY:
            if stub_retries < _MAX_STUB_RETRIES:
                yield self._category_request(cid, stub_retries + 1)
            return

        cards = response.css("div.item-wrap")
        if not cards:
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for card in cards:
            href = card.css("a::attr(href)").get() or ""
            match = _ITEM_ID_RE.search(href)
            if not match:
                continue
            item_id = match.group(1)

            name = " ".join(
                part.strip()
                for part in card.css("h2.pro_name::text").getall()
                if part.strip()
            )
            price = (
                "".join(card.css("span.price ::text").getall())
                .replace("¥", "")
                .replace("￥", "")
                .strip()
            )
            if not name or not price:
                continue
            if item_id in self.seen_ids:
                continue
            self.seen_ids.add(item_id)
            n += 1

            yield {
                "product_id": item_id,
                "product_name": name[:500],
                "category": str(cid),
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": f"https://m.111.com.cn/item/{item_id}.html",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        if n:
            logger.info("pharmacy_111: category %s yielded %d new products", cid, n)
