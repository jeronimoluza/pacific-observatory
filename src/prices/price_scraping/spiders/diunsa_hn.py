"""
Spider for Diunsa Honduras -- https://www.diunsa.hn/.

The storefront is a thin Angular/Next shell; all real data rides on a
separate multi-tenant commerce-platform API host, apicsm.dapplications.tech
("CSM" -- may power other Central American department-store domains in
future shards), found via a Playwright network trace of the homepage and a
category page load (the raw category HTML only carries a schema
placeholder "price":"0").

Two calls used here:
- GET /api/em/material_group/get_cb/1 -- full category tree for business
  id=1 (diunsa's tenant), 263 nodes; leaf categories (hasSubCategory="0",
  numeric code) are the walkable universe (171 confirmed live).
- POST /api/em/material/paginate?skip=N&take=N, JSON body
  {"businessPartner":1,"groupCode":"<leaf code>",...}, header
  x-company-id: DIUNSAPRD (required, taken from the site's own request) --
  returns `data[]` with newPrice/oldPrice HNL and `totalItems`.

Re-verified live 2026-08-17: groupCode=103 (a subcategory under
Electrónica) skip=0/take=15 vs skip=15/take=15 returned fully disjoint
`code` sets (0 overlap out of 117 totalItems) -- enumerability proven.
Sample item: "SMART TV JVC 43\" FHD GOOGLE TV", oldPrice 6490, newPrice
5790 HNL.
"""

import json
import logging
from datetime import datetime, timezone
from urllib.parse import quote

import scrapy

logger = logging.getLogger(__name__)

_API_BASE = "https://apicsm.dapplications.tech/api/em"
_GROUPS_URL = f"{_API_BASE}/material_group/get_cb/1"
_PAGINATE_URL = f"{_API_BASE}/material/paginate"
_HEADERS = {
    "x-company-id": "DIUNSAPRD",
    "content-type": "application/json",
    "canal": "WEB",
}
_GROUP_STRIDE = 4  # sample every Nth leaf category (~43 of 171)
PAGE_SIZE = 20
MAX_PAGES_PER_GROUP = 3


class DiunsaHnSpider(scrapy.Spider):
    name = "diunsa_hn"
    allowed_domains = ["dapplications.tech"]
    currency = "HNL"
    language = "es"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(_GROUPS_URL, callback=self.parse_groups, headers=_HEADERS)

    def parse_groups(self, response):
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"{self.name}: bad JSON at {response.url}")
            return
        leaves = [
            d.get("code")
            for d in data
            if d.get("hasSubCategory") == "0"
            and (d.get("code") or "").isdigit()
            and d.get("code") != "0"
        ]
        sampled = leaves[::_GROUP_STRIDE]
        logger.info(f"{self.name}: sampled {len(sampled)}/{len(leaves)} leaf groups")
        for group_code in sampled:
            yield self._page_request(group_code, skip=0)

    def _page_request(self, group_code, skip):
        body = {
            "businessPartner": 1,
            "storeId": None,
            "groupCode": group_code,
            "officeCode": "0",
            "type": "PD",
            "sortBy": "brand",
            "sortOption": "ASC",
            "search": "",
            "filter": {
                "priceMin": None,
                "priceMax": None,
                "brand": None,
                "supplier": None,
            },
            "source": "WEB",
            "hidden": "0",
            "isToLiquidation": None,
            "userIsAhorroMas": "0",
        }
        return scrapy.Request(
            f"{_PAGINATE_URL}?skip={skip}&take={PAGE_SIZE}",
            method="POST",
            headers=_HEADERS,
            body=json.dumps(body),
            callback=self.parse_page,
            meta={"group_code": group_code, "skip": skip},
        )

    def parse_page(self, response):
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"{self.name}: bad JSON at {response.url}")
            return
        rows = data.get("data") or []
        for row in rows:
            item = self._item(row)
            if item:
                yield item

        group_code = response.meta["group_code"]
        skip = response.meta["skip"]
        total_items = data.get("totalItems", 0)
        next_skip = skip + PAGE_SIZE
        if (
            rows
            and next_skip < total_items
            and next_skip < PAGE_SIZE * MAX_PAGES_PER_GROUP
        ):
            yield self._page_request(group_code, next_skip)

    def _item(self, row: dict):
        name = (row.get("name") or "").strip()
        code = row.get("code")
        if not name or not code:
            return None
        price = row.get("newPrice") or row.get("oldPrice")
        if not price:
            return None
        # The API's own `slug` field is always null; the frontend builds PDP
        # slugs client-side, so fall back to the site's own search URL
        # (confirmed live pattern: /todos?search=<term>) rather than guess it.
        url = f"https://www.diunsa.hn/todos?search={quote(name)}"
        return {
            "product_id": str(code),
            "product_name": name[:500],
            "category": row.get("materialGroupName"),
            "price": str(price),
            "currency": self.currency,
            "available": True,
            "url": url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
