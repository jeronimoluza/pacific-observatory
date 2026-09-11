"""
Woermann Fresh (Namibia) -- https://shop.woermannfresh.com/.

Woermann & Brock's ("wbsupers" on Facebook) online supermarket for
Windhoek, Namibia. Bespoke Vue/Laravel storefront (not Woo/Shopify) backed
by Elasticsearch. Discovered via OpenStreetMap shop=supermarket nodes
carrying a `website` tag (WebSearch budget was exhausted this pass) --
the brochure-only `woermann.com.na` corporate site links out to this
separate, genuinely transactional `shop.woermannfresh.com` subdomain.

No API call needed: each `/category/<slug>?page=N` page embeds the full
Elasticsearch response as an HTML-entity-encoded JSON string in the
`<elasticsearch-listing :default-search-result='...'>` custom-element
attribute -- `data['results'][i]['result']` carries title/slug/code
(barcode) plus `product_pricing[0].price` (VAT-inclusive) and
`was_price`. No auth, no TLS impersonation needed (plain UA clears it).

Page size is 100 (`pagination.size`); confirmed real pagination on the
`deodorant` category (163 items, 2 pages): page 1 returned 100 ids, page 2
returned 63 different ids, zero overlap.

Currency: no currency field in the payload, but this is unambiguously
Namibia (site chrome says "My Store: Windhoek", parent Woermann & Brock is
Namibian, VAT arithmetic on sampled rows is exactly 15% -- Namibia's VAT
rate, e.g. price_excluding_vat 29.56 * 0.15 = 4.434 ~= vat_amount 4.43) --
set NAD at the class level per the no-derive-from-symbol rule.

Category tree (70 leaf categories under 10 top-level groups: baby-care,
bakery, butchery, drinks, food-cupboard, fresh-food, frozen-foods,
household, outdoor, toiletries) summed to ~2,604 products across leaves
probed 2026-09-11 (some products may sit in >1 leaf, so this over-counts
slightly, but it's an order-of-magnitude confirmation this is a real,
large catalog -- not a broken/flat-count spider). food-relevant leaves
(bakery/butchery/drinks/food-cupboard/fresh-food/frozen-foods) are the
large majority of the tree; household/outdoor/toiletries are left in
(wide source, coicop_codes unset) rather than filtered, matching the
skill's supermarket-is-wide convention.

Page family: listing only (category pages carry the product data inline;
PDP pages are never fetched).
"""

from __future__ import annotations

import html
import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE = "https://shop.woermannfresh.com"


def _extract_balanced_attr(block: str, attr_marker: str) -> str | None:
    """Pull a single-quoted Vue prop value out of raw HTML, handling the
    fact the value itself never contains a raw `'` (Vue/Blade HTML-escapes
    quotes inside), so the first `'` followed by another attribute or `>`
    closes it."""
    m = re.search(re.escape(attr_marker), block)
    if not m:
        return None
    start = m.end()
    k = start
    while True:
        k = block.find("'", k)
        if k == -1:
            return None
        tail = block[k + 1 : k + 60].lstrip()
        if tail.startswith(":") or tail.startswith(">"):
            return block[start:k]
        k += 1


def _unescape(raw: str) -> str:
    return raw.replace("&quot;", '"').replace("&#039;", "'").replace("&amp;", "&")


class WoermannfreshNaSpider(scrapy.Spider):
    name = "woermannfresh_na"
    allowed_domains = ["shop.woermannfresh.com"]
    currency = "NAD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(BASE + "/", callback=self.parse_homepage)

    def parse_homepage(self, response):
        raw = _extract_balanced_attr(response.text, ":parent-categories='")
        if not raw:
            logger.warning("woermannfresh_na: could not find parent-categories on homepage")
            return
        try:
            cats = json.loads(_unescape(raw))
        except json.JSONDecodeError:
            logger.warning("woermannfresh_na: failed to parse category tree JSON")
            return

        leaf_paths: list[str] = []

        def walk(node):
            children = node.get("children") or []
            if not children:
                path = node.get("path") or node.get("slug")
                if path:
                    leaf_paths.append(path)
            else:
                for c in children:
                    walk(c)

        for c in cats:
            walk(c)

        seen = set()
        for slug in leaf_paths:
            if slug in seen:
                continue
            seen.add(slug)
            yield scrapy.Request(
                f"{BASE}/category/{slug}?page=1",
                callback=self.parse_category,
                meta={"slug": slug, "page": 1},
            )

    def parse_category(self, response):
        raw = _extract_balanced_attr(response.text, ":default-search-result='")
        if not raw:
            return
        try:
            data = json.loads(_unescape(raw))
        except json.JSONDecodeError:
            logger.warning("woermannfresh_na: bad JSON on %s", response.url)
            return

        for entry in data.get("results") or []:
            item = self._item(entry.get("result") or {})
            if item:
                yield item

        pagination = data.get("pagination") or {}
        page = response.meta["page"]
        if pagination.get("next"):
            slug = response.meta["slug"]
            yield scrapy.Request(
                f"{BASE}/category/{slug}?page={page + 1}",
                callback=self.parse_category,
                meta={"slug": slug, "page": page + 1},
            )

    def _item(self, r: dict):
        title = r.get("title")
        if not title:
            return None
        price = r.get("price")
        if price is None:
            return None
        try:
            if float(price) == 0:
                return None
        except (TypeError, ValueError):
            return None
        cats_hier = r.get("categories_hierarchy") or []
        category = " > ".join(
            c.get("title") for c in cats_hier if isinstance(c, dict) and c.get("title")
        ) or None
        slug = r.get("slug") or r.get("id")
        return {
            "product_id": str(r.get("code") or r.get("id") or ""),
            "product_name": html.unescape(str(title)).strip()[:500],
            "category": category,
            "price": str(price),
            "currency": self.currency,
            "available": bool(r.get("is_in_stock", True)),
            "url": f"{BASE}/product/{slug}",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
