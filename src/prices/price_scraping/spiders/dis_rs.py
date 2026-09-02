"""
Spider for DIS (Serbia) -- https://www.dis.rs/.

DIS is a Serbian supermarket chain. The storefront is a Next.js App
Router SPA that returns the identical app-shell HTML for every
`/artikli/<code>` route (confirmed live 2026-09-01: two different
product codes both returned a byte-identical 41,767-byte shell) -- all
real content loads client-side. A Playwright network trace found the
backing JSON API, which needs no auth and no session cookie:

  GET /api/Dis/Articles?page=<N>&pageSize=20
      -> {"totalCount": 6799, "data": [{"code","name","categoryCode",
           "categoryName","price","discountedPrice","attributes":{...}}]}
      `pageSize` is server-clamped to 20 regardless of the requested
      value; `page` is 1-indexed (page=0 and page=1 return the same
      first page). ~340 pages covers the full 6,799-item catalog.

  GET /api/Dis/Articles/{code}  -> single product, same shape.
  GET /api/Dis/Categories       -> [{"code","name"}] top-level departments
      (SVEŽE MESO I RIBA / fresh meat&fish, MLEKO... / dairy&eggs,
      SVEŽE VOĆE I POVRĆE / fresh fruit&veg, BEZALKOHOLNA PIĆA / soft
      drinks, ALKOHOLNA PIĆA / alcohol, HRANA ZA ŽIVOTINJE / pet food,
      KUĆNA HEMIJA / household chemistry, etc. -- not needed for the
      spider since /api/Dis/Articles already walks the whole catalog
      flat, but kept here for the record.)

Price field: `price` is 0 for most rows (no separate "was" price) and
`discountedPrice` carries the actual current selling price in every
sampled row; a genuine promo instead sets both (e.g. price=999.99,
discountedPrice=849.99). The spider always takes `discountedPrice`.

Currency: RSD (Serbian dinar), matches countries.yaml; no currency field
in the payload itself.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.dis.rs"
PAGE_SIZE = 20
MAX_PAGES = 400  # safety cap; catalog measured at ~340 pages (6,799 items)


class DisRsSpider(scrapy.Spider):
    name = "dis_rs"
    allowed_domains = ["dis.rs"]
    currency = "RSD"
    language = "sr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "DEFAULT_REQUEST_HEADERS": {"Referer": "https://www.dis.rs/"},
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(
            f"{_BASE}/api/Dis/Articles?page=1&pageSize={PAGE_SIZE}",
            callback=self.parse_page,
            meta={"page": 1},
        )

    def parse_page(self, response):
        page = response.meta["page"]
        try:
            data = response.json()
        except ValueError:
            return
        rows = data.get("data") or []
        logger.info(
            f"dis_rs: page={page} rows={len(rows)} total={data.get('totalCount')}"
        )
        scraped_at = datetime.now(timezone.utc).isoformat()
        for a in rows:
            price = a.get("discountedPrice") or a.get("price")
            if price is None or price <= 0:
                continue
            code = a.get("code")
            yield {
                "product_id": code,
                "product_name": (a.get("name") or "").strip()[:500],
                "category": a.get("categoryCode"),
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": f"{_BASE}/artikli/{code}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        if rows and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{_BASE}/api/Dis/Articles?page={nxt}&pageSize={PAGE_SIZE}",
                callback=self.parse_page,
                meta={"page": nxt},
            )
