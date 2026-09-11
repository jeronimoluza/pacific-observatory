"""
Heimkaup (Iceland) — https://www.heimkaup.is/.

Icelandic online store, today an alcohol / soft-drink / nicotine / snack
delivery catalogue (top-level sections: Beer, Wine, Spirits, Ready-to-Drink
Cocktails, Alcohol-Free, Nicotine, Soft drinks, Food, Gifts, Accessories).

The storefront is a React app running on the **Jiffy Grocery** white-label
platform (`REACT_APP_API_ROOT = https://api2.jiffygrocery.co.uk`,
`company = heimkaup`, warehouse `H495`), but every page is **server-side
rendered**: the HTML carries a complete `window.__INITIAL_STATE__` JSON blob
plus, on PDPs, a `schema.org/Product` JSON-LD block. So no Playwright and no
API reverse-engineering is needed — plain HTTP over the SSR pages is enough.

Walk:
  GET /                       -> `__INITIAL_STATE__.shopCategories`, the full
                                 category tree (10 roots, 136 nodes after
                                 flattening), each node giving a `<name>-<id>`
                                 slug.
  GET /c/<slug>               -> `__INITIAL_STATE__.catalogCategory.data.products`,
                                 a list of product records already carrying id,
                                 code/SKU, name, slug and price. Products are
                                 de-duplicated by product id across categories.

`prices.currency_code` is not exposed by the SSR state, but the PDP JSON-LD
states it: ISK. **Prices are integer minor units — divide by 100.** Verified
against the rendered page: `/p/gull-12x330ml-42708` state price `449000`,
rendered `4.490 kr.`, JSON-LD `"price": "4490.00"`, `"priceCurrency": "ISK"`.

Measured live 2026-09-11: 136 categories, 676 unique priced products. The SSR
listing renders only page 1 (48 items) and no `?page=` parameter is honoured
server-side, so the 8 categories holding more than 48 products are truncated;
because the tree is mostly leaves those products are still reached through
their own leaf category. Sample rows: 'Budweiser Budvar 6x500ml' ISK 3173,
'Heineken Lite 6x500ml' ISK 1899 (discounted from 2099).

Note the *stale sitemap trap*: `products-sitemap.xml` still lists 3,227 URLs
from Heimkaup's former general-merchandise catalogue (watches, phones,
Russian-slug category paths) and every one of those PDPs now 404s. Do not
seed off the sitemap — walk the category tree from the home page instead.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.heimkaup.is"
_STATE_RE = re.compile(
    r"window\.__INITIAL_STATE__\s*=\s*(.*?)</script>", re.S
)
# Jiffy stores money as integer minor units; ISK is displayed in whole krónur.
_MINOR_UNIT_DIVISOR = 100


def _parse_state(text: str) -> dict | None:
    m = _STATE_RE.search(text)
    if not m:
        return None
    try:
        return json.loads(m.group(1).strip().rstrip(";"))
    except (json.JSONDecodeError, ValueError):
        return None


class HeimkaupIsSpider(scrapy.Spider):
    name = "heimkaup_is"
    allowed_domains = ["heimkaup.is"]
    currency = "ISK"
    language = "is"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seen_ids: set = set()

    async def start(self):
        yield scrapy.Request(
            f"{BASE_URL}/",
            callback=self.parse_home,
            errback=self.errback,
        )

    def parse_home(self, response):
        state = _parse_state(response.text)
        if not state:
            logger.error(f"{self.name}: no __INITIAL_STATE__ on {response.url}")
            return
        slugs: list[str] = []

        def flatten(nodes):
            for node in nodes or []:
                category = node.get("category") or {}
                slug = category.get("slug")
                if slug:
                    slugs.append(slug)
                flatten(node.get("children"))

        flatten(state.get("shopCategories"))
        logger.info(f"{self.name}: {len(slugs)} categories in the shop tree")
        for slug in slugs:
            yield scrapy.Request(
                f"{BASE_URL}/c/{slug}",
                callback=self.parse_category,
                errback=self.errback,
                meta={"category_slug": slug},
            )

    def parse_category(self, response):
        state = _parse_state(response.text)
        if not state:
            logger.warning(f"{self.name}: no state on {response.url}")
            return
        block = (state.get("catalogCategory") or {}).get("data") or {}
        category_name = (block.get("category") or {}).get("name")
        rows = block.get("products") or []

        emitted = 0
        for row in rows:
            pid = row.get("id")
            if pid is None or pid in self._seen_ids:
                continue
            name = (row.get("name") or "").strip()
            slug = row.get("slug")
            if not name or not slug:
                continue
            raw_price = row.get("discountPrice")
            if raw_price is None:
                raw_price = row.get("price")
            if raw_price is None:
                continue
            self._seen_ids.add(pid)
            emitted += 1
            stock = row.get("sellableWarehouses") or {}
            yield {
                "product_id": str(row.get("code") or pid),
                "product_name": name[:500],
                "category": category_name,
                "price": str(raw_price / _MINOR_UNIT_DIVISOR),
                "currency": self.currency,
                "available": any(bool(v) for v in stock.values()),
                "url": f"{BASE_URL}/p/{slug}",
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        logger.info(
            f"{self.name}: category={response.meta.get('category_slug')!r} "
            f"got={len(rows)} new={emitted} total_seen={len(self._seen_ids)}"
        )

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
