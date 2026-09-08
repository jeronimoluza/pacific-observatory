"""
Vínbúðin / ÁTVR (Iceland) — https://www.vinbudin.is/.

Iceland's state alcohol retail monopoly. Every alcoholic beverage sold at
retail in Iceland is sold here, at a single nationally-uniform price, so this
is effectively an official national price list for COICOP 02.1 rather than
one competitor's shelf.

Tier 1B. The product page (/heim/vorur/vorur.aspx) is a contentXXL/ASP.NET
WebForms shell whose grid is rendered by React from an ASMX ScriptService.
A Playwright network trace of that page showed the grid calling:

    GET /addons/origo/module/ajaxwebservices/search.asmx/DoSearch
        ?&skip=<n>&count=<n>&orderBy=name%20asc

TWO NON-OBVIOUS REQUIREMENTS, both found by probing and both fatal if missed:

1. The request MUST carry `Content-Type: application/json; charset=utf-8`
   even though it is a GET. Without it ASP.NET falls back to XML
   serialization and returns HTTP 500 "Cannot serialize interface
   System.Collections.IEnumerable" for every call. That 500 is what a naive
   probe sees, and it looks like a dead endpoint rather than a missing header.
2. The response is DOUBLE-ENCODED: the ScriptService envelope is
   `{"d": "<json string>"}`, and that string parses to
   `{"data": [...], "total": <int>}`. One json.loads is not enough.

Enumerability proven 2026-09-05: skip=0 and skip=100 (count=100) return 100
distinct ProductIDs each with zero overlap; `total` reports 4,167 products and
count=500 is honoured, so this is a walkable catalogue and not a carousel.

Prices are whole ISK krónur in `ProductPrice` (float, no minor-unit scaling).
`ProductCategory.name` gives the beverage class (red / white / beer / ...),
emitted as `category` so the classifier can separate the 02.1.x leaves.

SPIDER PAGE FAMILY: API (no HTML page is ever fetched). Emitted URLs are
synthetic permalinks to the site's own product-detail route; the spider does
not fetch them, so they cannot be used to validate an archive regex locally.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_API = (
    "https://www.vinbudin.is/addons/origo/module/ajaxwebservices"
    "/search.asmx/DoSearch"
)
_PAGE_SIZE = 100
_MAX_PAGES = 200  # safety valve; 4,167 products is ~42 pages


class VinbudinIsSpider(scrapy.Spider):
    name = "vinbudin_is"
    allowed_domains = ["vinbudin.is"]
    currency = "ISK"
    language = "is"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "DEFAULT_REQUEST_HEADERS": {
            # Mandatory: without this the ASMX endpoint 500s on every call.
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
            "Referer": "https://www.vinbudin.is/heim/vorur/vorur.aspx",
            "X-Requested-With": "XMLHttpRequest",
        },
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    @staticmethod
    def _page_url(skip: int) -> str:
        return f"{_API}?&skip={skip}&count={_PAGE_SIZE}&orderBy=name%20asc"

    async def start(self):
        yield scrapy.Request(
            self._page_url(0), callback=self.parse_page, meta={"skip": 0}
        )

    def parse_page(self, response):
        payload = self._decode(response.text)
        if payload is None:
            logger.warning(f"{self.name}: undecodable payload at {response.url}")
            return
        items = payload.get("data") or []
        total = payload.get("total")
        skip = response.meta["skip"]
        logger.info(f"{self.name} skip={skip} count={len(items)} total={total}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in items:
            row = self._item(p, scraped_at)
            if row:
                yield row
        if len(items) >= _PAGE_SIZE and (skip // _PAGE_SIZE) + 1 < _MAX_PAGES:
            nxt = skip + _PAGE_SIZE
            yield scrapy.Request(
                self._page_url(nxt), callback=self.parse_page, meta={"skip": nxt}
            )

    @staticmethod
    def _decode(text: str) -> dict | None:
        """Unwrap the ScriptService double encoding: {"d": "<json>"}."""
        try:
            outer = json.loads(text)
        except ValueError:
            return None
        inner = outer.get("d") if isinstance(outer, dict) else outer
        if isinstance(inner, str):
            try:
                inner = json.loads(inner)
            except ValueError:
                return None
        return inner if isinstance(inner, dict) else None

    def _item(self, p: dict, scraped_at: str) -> dict | None:
        name = p.get("ProductName")
        price = p.get("ProductPrice")
        pid = p.get("ProductID")
        if not name or price is None or pid is None:
            return None
        try:
            value = float(price)
        except (TypeError, ValueError):
            return None
        if value <= 0:
            return None
        category = p.get("ProductCategory")
        if isinstance(category, dict):
            category = category.get("name")
        volume = p.get("ProductBottledVolume")
        return {
            "product_id": str(pid),
            "product_name": str(name).strip()[:500],
            "category": str(category) if category else None,
            "price": str(value),
            "currency": self.currency,
            "available": bool(p.get("ProductInventory") or 0),
            "url": f"https://www.vinbudin.is/heim/vorur/stoek-vara.aspx/?productid={pid}",
            "language": self.language,
            "unit_info": f"{volume:g} ml" if isinstance(volume, (int, float)) else None,
            "scraped_at_utc": scraped_at,
        }
