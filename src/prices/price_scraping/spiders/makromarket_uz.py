"""Spider for MakroMarket (Uzbekistan) -- https://makromarket.uz/.

Next.js storefront (App Router, client components -- no SSR hydration blob
in the raw HTML) backed by an open, unauthenticated JSON API on a separate
subdomain: `api.makromarket.uz/api/v2/product-list/?category=<id>&limit=N&
offset=M` (found via a one-time Playwright network trace, per the brief's
discovery-only allowance -- this spider itself makes plain GET requests,
no browser at collection time). `api/v2/category-list/` gives the fixed set
of 11 curated top-level collections (there is no deeper department
taxonomy exposed); each is walked to exhaustion via `count`/`next`.

korzinka.uz (Uzbekistan's largest chain) was probed first and dropped: it
serves a Cloudflare "Just a moment..." challenge on plain curl (market
leader, WAF-hardened per the inverse-correlation law). MakroMarket is a
smaller Tashkent-based chain that verified on the first API guess.

Re-verified live 2026-08-06: /api/v2/product-list/?category=520 -> 200,
real meat-department SKUs incl. 'Rozovaya dudlangan kolbasa Alpiy 1 kg'
UZS 104950, 'Gov MS Maxsus Sagban qaynatilgan kolbasa 1 kg' UZS 74950.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_API = "https://api.makromarket.uz/api/v2"
_PAGE_SIZE = 100
MAX_PAGES = 30


class MakromarketUzSpider(scrapy.Spider):
    name = "makromarket_uz"
    allowed_domains = ["makromarket.uz", "api.makromarket.uz"]
    currency = "UZS"
    language = "uz"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(
            f"{_API}/category-list/",
            callback=self.parse_categories,
            headers={"Accept": "application/json"},
        )

    def parse_categories(self, response):
        cats = response.json()
        logger.info(f"{self.name}: {len(cats)} categories")
        for cat in cats:
            yield scrapy.Request(
                f"{_API}/product-list/?category={cat['id']}&limit={_PAGE_SIZE}&offset=0",
                callback=self.parse_products,
                headers={"Accept": "application/json"},
                meta={"category": cat["title"], "offset": 0},
            )

    def parse_products(self, response):
        data = response.json()
        if isinstance(data, list):
            results, count, has_next = data, len(data), False
        else:
            results = data.get("results") or []
            count = data.get("count") or 0
            has_next = bool(data.get("next"))
        category = response.meta["category"]
        offset = response.meta["offset"]
        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in results:
            price = p.get("newPrice")
            name = p.get("title")
            if not name or price is None:
                continue
            yield {
                "product_id": str(p.get("id")),
                "product_name": str(name).strip()[:500],
                "category": category,
                "price": price,
                "currency": self.currency,
                "available": p.get("status") == 1,
                "url": f"https://makromarket.uz/product/{p.get('id')}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(
            f"{self.name}: {category} offset={offset} results={len(results)} count={count}"
        )

        if has_next and offset + _PAGE_SIZE < count:
            next_offset = offset + _PAGE_SIZE
            if next_offset < MAX_PAGES * _PAGE_SIZE:
                cat_id = response.url.split("category=")[1].split("&")[0]
                yield scrapy.Request(
                    f"{_API}/product-list/?category={cat_id}&limit={_PAGE_SIZE}&offset={next_offset}",
                    callback=self.parse_products,
                    headers={"Accept": "application/json"},
                    meta={"category": category, "offset": next_offset},
                )
