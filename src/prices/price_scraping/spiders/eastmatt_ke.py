"""
Eastmatt (Kenya) -- https://www.eastmatt.com/.

Regional Kenyan supermarket chain (11 branches, strongest outside
Nairobi -- Kitengela, Kajiado, Athi River, etc.). The shard's seed domain
`eastmatt.co.ke` does not resolve; the real online-ordering site is
`eastmatt.com` (`eastmatt.co.ke` is only used as an email domain).

The homepage is a plain server-rendered PHP catalogue
(`item-list.php?CategoryID=<id>&branch=KITENGELA`) whose "load more"
button calls a fully open JSON API with no auth:

    GET /ios1/itemdepartment2.php?DepartmentID=<id>&branch=KITENGELA
        &CategoryID=&Type=Department&limit=48&page=N

Verified live 2026-09-06: DepartmentID=2 alone returns
`{"total_items": 1677, "total_pages": 35}`; page 1 vs page 2 of a
category-scoped call (CategoryID=101) returned zero id overlap across 48
items each -- genuine pagination. Prices are plain KSH decimals
(`Price`/`FinalPrice`), e.g. "SAFISHA BLEACH REGULAR 750ML" KSH 205.00.

`branches.php` only exposes `branch=KITENGELA` for the online-ordering
flow (the 10 other physical branches shown on the site have no online
catalogue), so the spider is single-branch by design.

Walking by top-level DepartmentID (2-9, from the homepage nav) rather
than by CategoryID covers the whole catalogue without needing to
enumerate every CategoryID first.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.eastmatt.com/ios1/itemdepartment2.php"
_BRANCH = "KITENGELA"
_DEPARTMENT_IDS = [2, 3, 4, 5, 6, 7, 8, 9]
PAGE_LIMIT = 48
MAX_PAGES_PER_DEPT = 6  # safety cap: ~288 items/department


class EastmattKeSpider(scrapy.Spider):
    name = "eastmatt_ke"
    allowed_domains = ["eastmatt.com"]
    currency = "KES"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "DOWNLOAD_TIMEOUT": 60,
    }

    async def start(self):
        for dept_id in _DEPARTMENT_IDS:
            yield self._page_request(dept_id, 1)

    def _page_request(self, dept_id, page):
        url = (
            f"{_BASE}?DepartmentID={dept_id}&branch={_BRANCH}"
            f"&CategoryID=&Type=Department&limit={PAGE_LIMIT}&page={page}"
        )
        return scrapy.Request(
            url,
            callback=self.parse_page,
            meta={"dept_id": dept_id, "page": page},
        )

    def parse_page(self, response):
        dept_id = response.meta["dept_id"]
        page = response.meta["page"]
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"eastmatt_ke: non-JSON response dept_id={dept_id} page={page}")
            return
        rows = data.get("items") or []
        n = 0
        for row in rows:
            item = self._item(row, dept_id)
            if item:
                n += 1
                yield item
        logger.info(f"eastmatt_ke: dept={dept_id} page={page} items={n}")

        if len(rows) >= PAGE_LIMIT and page < MAX_PAGES_PER_DEPT:
            yield self._page_request(dept_id, page + 1)

    def _item(self, row, dept_id):
        name = row.get("Description")
        price = row.get("FinalPrice") or row.get("Price")
        item_id = row.get("ID")
        if not name or price in (None, ""):
            return None
        try:
            price_val = float(price)
        except (TypeError, ValueError):
            return None
        if price_val <= 0:
            return None
        return {
            "product_id": str(item_id) if item_id else None,
            "product_name": str(name).strip()[:500],
            "price": str(price_val),
            "currency": self.currency,
            "category": f"dept-{dept_id}-sub-{row.get('SubCategoryID')}"
            if row.get("SubCategoryID")
            else f"dept-{dept_id}",
            "url": f"https://www.eastmatt.com/item-details.php?ItemID={item_id}"
            if item_id
            else None,
            "available": True,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
