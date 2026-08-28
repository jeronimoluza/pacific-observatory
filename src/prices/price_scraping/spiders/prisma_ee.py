"""
Spider for Prisma Estonia (S Group) — https://www.prismamarket.ee/.

Next.js SSR. Every /tooted/<slug> category page embeds a full Apollo cache
in `__NEXT_DATA__.props.pageProps.apolloState`, including BOTH the site's
entire category tree (a `Store` entry with a recursively-nested
`navigation` array — 25 top-level departments, 975 leaf slugs, re-verified
live 2026-08-06) and that page's own product listing (`Product` entries
with id/name/price/priceUnit/slug — no separate PDP fetch needed). We
fetch one seed category page, harvest the full leaf-slug tree from its
`Store.navigation`, then crawl every leaf slug once — no hardcoded
category list required, unlike the other SSR-HTML sources in this batch.

Sample: /tooted/puu-ja-koogiviljad -> 'Kartul punane pesemata KG'
price=0.25 EUR/priceUnit=KPL (comparisonPrice 0.98 EUR/KG).

api.s-kaupat.fi-style GraphQL backend (graphql-api.prismamarket.ee) exists
but requires a session/store context we don't have — the SSR HTML path
above sidesteps it entirely.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.prismamarket.ee"
_SEED_SLUG = "puu-ja-koogiviljad"
_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def _collect_leaf_slugs(nav_items) -> list[str]:
    leaves = []
    for item in nav_items or []:
        children = item.get("children") or []
        if children:
            leaves.extend(_collect_leaf_slugs(children))
        elif item.get("slug"):
            leaves.append(item["slug"])
    return leaves


def _apollo_state(response_text):
    m = _NEXT_DATA_RE.search(response_text)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None
    return data.get("props", {}).get("pageProps", {}).get("apolloState", {})


class PrismaEeSpider(scrapy.Spider):
    name = "prisma_ee"
    allowed_domains = ["prismamarket.ee"]
    currency = "EUR"
    language = "et"

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
        yield scrapy.Request(f"{_BASE}/tooted/{_SEED_SLUG}", callback=self.parse_seed)

    def parse_seed(self, response):
        apollo = _apollo_state(response.text) or {}
        store = next(
            (
                v
                for v in apollo.values()
                if isinstance(v, dict) and v.get("__typename") == "Store"
            ),
            None,
        )
        if not store:
            logger.error("prisma_ee: no Store navigation found on seed page")
            return
        leaves = sorted(set(_collect_leaf_slugs(store.get("navigation"))))
        logger.info(f"prisma_ee: {len(leaves)} leaf categories to walk")
        yield from self._parse_products(apollo, _SEED_SLUG, response.text)
        for slug in leaves:
            if slug == _SEED_SLUG:
                continue
            yield scrapy.Request(
                f"{_BASE}/tooted/{slug}",
                callback=self.parse_category,
                meta={"slug": slug},
            )

    def parse_category(self, response):
        apollo = _apollo_state(response.text) or {}
        yield from self._parse_products(apollo, response.meta["slug"], response.text)

    def _parse_products(self, apollo, category, raw_text):
        scraped_at = datetime.now(timezone.utc).isoformat()
        products = [
            v
            for v in apollo.values()
            if isinstance(v, dict) and v.get("__typename") == "Product"
        ]
        logger.info(f"prisma_ee: {category} products={len(products)}")
        for p in products:
            name = p.get("name")
            price = p.get("price")
            if not name or price is None:
                continue
            yield {
                "product_id": str(p.get("ean") or p.get("id") or ""),
                "product_name": name.strip()[:500],
                "category": category,
                "price": str(price),
                "currency": self.currency,
                "available": True,
                "url": f"{_BASE}/toode/{p.get('slug')}" if p.get("slug") else _BASE,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
