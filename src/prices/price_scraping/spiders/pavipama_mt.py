"""
Spider for PaviPama (Malta) — https://www.pavipama.com.mt/.

Public JSON API on the pavipama.com.mt origin (needs Origin/Referer headers
set to the www subdomain; plain curl without them still returns 200 in
practice, but we send them anyway to match the confirmed-working probe).
GET /api/cli/ecommerce/products/featured?p=0&store= turns out to be the
full paginated catalog browse, not a curated "featured" subset —
totalElements=3191 across totalPages=160 at size=20 (re-verified live
2026-08-06) — so we walk p=0..totalPages-1 once, no per-category crawl
needed.

Sample: 'ACQUA FRIZZANTE 500ML' price=0.25 EUR (netPrice/promotions also
present; `price` is the shelf price actually charged).

Note: pavishopping.com (the domain implied by an older CSV export) is DEAD
(NXDOMAIN); the live domain is pavipama.com.mt, found via search during
probing.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_API = "https://pavipama.com.mt/api/cli/ecommerce/products/featured"
_HEADERS = {
    "Origin": "https://www.pavipama.com.mt",
    "Referer": "https://www.pavipama.com.mt/",
    "Accept": "application/json",
}
MAX_PAGES = 400


class PavipamaMtSpider(scrapy.Spider):
    name = "pavipama_mt"
    allowed_domains = ["pavipama.com.mt"]
    currency = "EUR"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(
            f"{_API}?p=0&store=",
            callback=self.parse_page,
            headers=_HEADERS,
            meta={"page": 0},
        )

    def parse_page(self, response):
        try:
            payload = response.json()
        except ValueError:
            logger.warning(f"pavipama_mt: non-JSON at {response.url}")
            return
        page = response.meta["page"]
        products = payload.get("data") or []
        total_pages = payload.get("totalPages") or 1
        logger.info(f"pavipama_mt: page={page}/{total_pages} products={len(products)}")

        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in products:
            item = self._item(p, scraped_at)
            if item:
                yield item

        nxt = page + 1
        if products and nxt < total_pages and nxt < MAX_PAGES:
            yield scrapy.Request(
                f"{_API}?p={nxt}&store=",
                callback=self.parse_page,
                headers=_HEADERS,
                meta={"page": nxt},
            )

    def _item(self, p, scraped_at):
        name = p.get("description")
        price = p.get("price")
        if not name or price is None:
            return None
        return {
            "product_id": str(p.get("ref") or p.get("id") or ""),
            "product_name": name.strip()[:500],
            "category": p.get("categoryDescription"),
            "price": str(price),
            "currency": self.currency,
            "available": bool(p.get("enabled", True)),
            "url": p.get("imageUrl") or "https://www.pavipama.com.mt/",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
