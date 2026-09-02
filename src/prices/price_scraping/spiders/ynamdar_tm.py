"""
Ynamdar Online Market (Turkmenistan) — https://ynamdar.com/.

Re-discovered 2026-08-31: the ashgabatmarket_tm.yaml notes record an
earlier "Ynamdar" probe as dead, but that check hit `ynamdar.tm`/
`ynamdar.com.tm` (expired cert). The plain `.com` domain is live and is a
different, much larger property: "Ynamdar Online Market", a Nuxt 3 app
serving Ashgabat (single active region, code "ag" per
`/market-api/regions`).

Homepage is server-rendered with a Nuxt `__NUXT_DATA__` payload (real
product data inline), but full catalogue browsing needs the JSON API
found by grepping the bundled JS for the `$http` client class: it builds
per-service clients as `<same-origin>/market-api/`, `/store-api/`,
`/food-api/` etc, NOT `https://api.ynamdar.com` (that hostname 404s on
every path tried -- a stale/unused subdomain). Confirmed endpoints, both
same-origin, no auth, no special headers:

    GET  https://ynamdar.com/market-api/categories
         -> full nested category tree (14 top-level, 200 leaf nodes)
    POST https://ynamdar.com/market-api/category/products
         body: {"page": N, "category-id": "<uuid>"}
         -> {"status":"SUCCESS","result":{"total","current","products",
             "has-next"}}

Verified pagination genuinely advances: page=1 vs page=2 for the same
category share 0 of 24/24 product ids (the URL's own `?page=` query
param does nothing -- SSR always renders page 1 from a cache key that
ignores it; page 2+ only exists via this POST, matching brief rule #7).

Walked every LEAF category (200 of them) rather than parents, to avoid
inflating counts via parent/child aggregation. One cross-cutting branch
("Распродажи и Акции" / sales-and-promos, including a 4,395-item
"discounted products" bucket) mixes items already reachable from their
real merchandising category, so a spider-wide `product_id` dedup set is
used -- first category encountered wins the `category` label, later
duplicates are dropped, matching the "always count DISTINCT ids" rule.

Prices are integer minor units (TMT * 100): sample "Кофе Carte Noir
White 3в1" sale-price 510 -> 5.10 TMT implausible for the item, but
"Кукуруза консервированная Heinz 400 г" sale-price 4350 -> 43.50 TMT is
right for canned corn, and Axe shower gel 250ml old-price 4200/
sale-price 3780 -> 42.00/37.80 TMT matches a real markdown. Divided by
100 here. Currency is TMT (matches countries.yaml; site has no
currency/region switcher outside Ashgabat).

There IS a routable, real product page (unlike halkmarket_tm's SPA-only
listing): `/ru/ag/product/<code>` server-renders with the product name
in the HTML -- verified for code "CRN1100114" (Heinz corn) and
"1100114" (Carte Noir coffee).

Catalogue is a genuine wide supermarket assortment (food + household +
cosmetics + baby + pet), not food-only -- typical for an online
hypermarket. Food-relevant branches (leaf totals from the live category
tree, 2026-08-31): Продукты питания, кулинария (food/culinary, ~9,500
across its subtree), Молочные продукты/яйца/завтрак (dairy/eggs/
breakfast), Мясная продукция (meat), Фрукты и овощи (fruit/veg),
Напитки безалкогольные (soft drinks), Правильное питание (healthy
eating), Для детей > Детское питание (baby food) -- these substantially
outweigh the non-food branches (cosmetics, cleaning, home, stationery,
pet food).
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://ynamdar.com"


class YnamdarTmSpider(scrapy.Spider):
    name = "ynamdar_tm"
    allowed_domains = ["ynamdar.com"]
    currency = "TMT"
    language = "ru"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.25,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_ids: set[str] = set()

    async def start(self):
        yield scrapy.Request(
            f"{BASE_URL}/market-api/categories",
            headers={"Accept": "application/json"},
            callback=self.parse_categories,
            errback=self.errback,
        )

    def parse_categories(self, response):
        try:
            payload = response.json()
        except ValueError:
            logger.error(f"{self.name}: non-JSON categories response")
            return
        tree = payload.get("result") or []
        leaves = []
        self._collect_leaves(tree, [], leaves)
        logger.info(f"{self.name}: {len(leaves)} leaf categories discovered")
        for cid, breadcrumb in leaves:
            yield self._api_request(cid, breadcrumb, page=1)

    def _collect_leaves(self, nodes, path, out):
        for node in nodes:
            name = (
                (node.get("name") or {}).get("ru")
                or (node.get("name") or {}).get("tm")
                or ""
            )
            children = node.get("children") or []
            new_path = path + [name]
            if children:
                self._collect_leaves(children, new_path, out)
            else:
                out.append((node["id"], " > ".join(new_path)))

    def _api_request(self, category_id, breadcrumb, page):
        return scrapy.Request(
            f"{BASE_URL}/market-api/category/products",
            method="POST",
            body=json.dumps({"page": page, "category-id": category_id}),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            callback=self.parse_products,
            errback=self.errback,
            meta={"category_id": category_id, "breadcrumb": breadcrumb, "page": page},
            dont_filter=True,
        )

    def parse_products(self, response):
        category_id = response.meta["category_id"]
        breadcrumb = response.meta["breadcrumb"]
        page = response.meta["page"]
        try:
            payload = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON products response for {breadcrumb}")
            return
        result = payload.get("result") or {}
        products = result.get("products") or []
        total = result.get("total", 0)
        has_next = result.get("has-next", False)

        for p in products:
            pid = p.get("id")
            if not pid or pid in self.seen_ids:
                continue
            name = (
                (p.get("name") or {}).get("ru") or (p.get("name") or {}).get("tm") or ""
            ).strip()
            price = p.get("sale-price")
            if price is None:
                price = p.get("old-price")
            code = p.get("code")
            if not name or price is None or not code:
                continue
            self.seen_ids.add(pid)
            yield {
                "product_id": pid,
                "product_name": name[:500],
                "category": breadcrumb,
                "price": str(price / 100),
                "currency": self.currency,
                "available": not p.get("out-of-stock", False),
                "url": f"{BASE_URL}/ru/ag/product/{code}",
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        logger.info(
            f"{self.name}: category={breadcrumb} page={page} got={len(products)} "
            f"total={total} has-next={has_next}"
        )

        if has_next and products:
            yield self._api_request(category_id, breadcrumb, page + 1)

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
