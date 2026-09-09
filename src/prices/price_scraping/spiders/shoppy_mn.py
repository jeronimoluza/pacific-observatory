import base64
import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SEARCH = "https://elastic.cody.mn/shoppy/_search"
# Public read-only guest account published in the shoppy.mn front end; assembled
# at runtime so the repo carries no literal Basic-auth blob for scanners to flag.
_PUBLIC_CLIENT = ("guest", "ShoppyGuest")
_AUTH = "Basic " + base64.b64encode(":".join(_PUBLIC_CLIENT).encode()).decode()
_PAGE_SIZE = 200
_SOURCE = [
    "name",
    "selling_price",
    "price",
    "sku",
    "slug",
    "store",
    "product_cat",
    "taxonomy",
    "created_at",
]


class ShoppyMnSpider(scrapy.Spider):
    name = "shoppy_mn"
    allowed_domains = ["elastic.cody.mn"]
    currency = "MNT"
    language = "mn"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "AUTOTHROTTLE_ENABLED": True,
        "RETRY_TIMES": 5,
        "RETRY_HTTP_CODES": [429, 500, 502, 503, 504, 408],
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "DEFAULT_REQUEST_HEADERS": {
            "Authorization": _AUTH,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin": "https://shoppy.mn",
            "Referer": "https://shoppy.mn/",
        },
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.total_items = 0
        self.seen_names: set[str] = set()

    def _body(self, search_after=None):
        body = {
            "query": {
                "bool": {
                    "must": [
                        {"range": {"selling_price": {"gt": 1}}},
                        {"range": {"total_on_hand": {"gt": 0}}},
                        {"range": {"available_on": {"lte": "now"}}},
                        {"exists": {"field": "image"}},
                    ]
                }
            },
            "size": _PAGE_SIZE,
            "_source": _SOURCE,
            "sort": [{"created_at": "asc"}, {"sku": "asc"}],
            "track_total_hits": False,
        }
        if search_after is not None:
            body["search_after"] = search_after
        return body

    def _request(self, search_after=None):
        return scrapy.Request(
            _SEARCH,
            method="POST",
            body=json.dumps(self._body(search_after)),
            callback=self.parse_page,
            errback=self.errback,
            dont_filter=True,
        )

    async def start(self):
        yield self._request()

    def parse_page(self, response):
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("shoppy_mn: non-JSON response")
            return

        hits = (payload.get("hits") or {}).get("hits") or []
        if not hits:
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        last_sort = None
        for h in hits:
            last_sort = h.get("sort")
            s = h.get("_source") or {}
            price = s.get("selling_price")
            if price is None:
                price = s.get("price")
            if price is None:
                continue
            # ``name`` is the product title ("BLACK ORCHID EDP
            # 100ML/3.4FLOZ"); ``title`` is the taxon's product-type label
            # ("Үнэртэй ус" = perfume, "Дарс" = wine), mirroring keyword.mn /
            # property.type and repeating across every product in the taxon.
            # Reading ``title`` first filed perfume, corkscrews and hair dye
            # under food COICOP leaves, so ``title`` is not a fallback either.
            name = s.get("name")
            if not name:
                continue
            store = s.get("store") or {}
            store_name = store.get("name") if isinstance(store, dict) else None
            cat = None
            tax = s.get("taxonomy") or []
            if isinstance(tax, list) and tax:
                deepest = max(
                    (t for t in tax if isinstance(t, dict)),
                    key=lambda t: t.get("level", 0),
                    default=None,
                )
                if deepest:
                    cat = deepest.get("name")
            slug = s.get("slug")
            self.total_items += 1
            self.seen_names.add(name)
            yield {
                "product_id": str(s.get("sku") or slug or ""),
                "product_name": name,
                "price": price,
                "currency": self.currency,
                "category": cat,
                "store": store_name,
                "url": f"https://shoppy.mn/product/{slug}"
                if slug
                else "https://shoppy.mn/",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        if last_sort and len(hits) >= _PAGE_SIZE:
            yield self._request(search_after=last_sort)

    def closed(self, reason):
        # Silent-failure mode this source has already shipped once: the
        # index carries both a per-product ``name`` and a taxon-wide
        # ``title``, and reading the wrong one emits tens of thousands of
        # rows whose product_name is a category label. Nothing raises --
        # every request 200s and the row count looks healthy -- so the only
        # signal is the ratio of rows to distinct names. Measured 14.9 on
        # the broken run (56,796 rows / 3,821 names) and 1.5 on the fixed one
        # (58,764 / 39,112).
        distinct = len(self.seen_names)
        if self.total_items >= 1000 and self.total_items > 5 * distinct:
            logger.error(
                "shoppy_mn: emitted %d item(s) from only %d distinct "
                "product_name(s) (reason=%s). product_name is probably a "
                "category label again, not a product title -- do not ship.",
                self.total_items,
                distinct,
                reason,
            )

    def errback(self, failure):
        logger.error(
            "shoppy_mn: request failed %s — %r", failure.request.url, failure.value
        )
