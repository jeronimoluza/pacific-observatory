"""
Shared base class for Shopify storefront spiders.

Shopify exposes an unauthenticated catalog at /products.json?limit=250&page=N
(some tenants only expose one collection, e.g.
/collections/grocery/products.json — override PRODUCTS_PATH for those).
This base paginates to exhaustion, flattening one row per variant (appending
the variant title to the product title unless it is "Default Title").

Subclasses set: name, allowed_domains, base_url, currency, language.
Optionally override PRODUCTS_PATH (default "/products.json").

Underscored filename — Scrapy's SpiderLoader skips classes without `name`.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

PER_PAGE = 250
MAX_PAGES = 200  # safety cap

# --- archived-HTML parsing (Wayback/CC replay) -----------------------------
#
# The live spider reads the /products.json catalog endpoint; archived
# snapshots are storefront product-DETAIL HTML, a different surface. These
# helpers are pure functions (no Scrapy Response, no network, no class
# state) tried in order of reliability, richest first:
#
#   1. The inline `<script id="ProductJson-...">` blob some themes embed —
#      the exact shape of one /products.json entry (variants carry title,
#      sku, available, price in CENTS).
#   2. The `var meta = {"product": {...}}` / window.ShopifyAnalytics.meta
#      blob nearly every Shopify theme embeds for analytics — variants carry
#      name (already "Title - Variant"), sku, price in CENTS, but no
#      `available` flag.
#   3. JSON-LD `<script type="application/ld+json">` with `"@type":
#      "Product"` — offers carry price as a DECIMAL string/number.
#   4. OpenGraph `<meta property="og:price:amount" ...>` — decimal, single
#      price only (last resort).
#
# Tiers 1/2 report price in cents; tiers 3/4 report the decimal price.
# Divide by 100 only for tiers 1/2 — verified against the same page's
# JSON-LD/og: decimal price to catch the 100x error.
_PRODUCT_JSON_RE = re.compile(
    r'<script[^>]*type=["\']application/json["\'][^>]*id=["\']ProductJson[^"\']*["\'][^>]*>'
    r"(.*?)</script>",
    re.S | re.I,
)
_ANALYTICS_META_RE = re.compile(r"var meta = (\{.*?\});", re.S)
_LDJSON_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S | re.I
)
_META_TAG_RE = re.compile(r"<meta\b[^>]*>", re.I)
_META_PROP_RE = re.compile(r'property=["\']([^"\']+)["\']')
_META_CONTENT_RE = re.compile(r'content=["\']([^"\']*)["\']')


def _rows_from_product_json(html: str, base_url: str):
    """Tier 1: full inline product JSON (same shape as one /products.json entry)."""
    m = _PRODUCT_JSON_RE.search(html)
    if not m:
        return None
    try:
        data = json.loads(m.group(1).strip())
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    title = (data.get("title") or "").strip()
    variants = data.get("variants") or []
    if not (title and variants):
        return None
    category = data.get("type") or data.get("product_type") or None
    handle = data.get("handle") or ""
    rows = []
    for v in variants:
        if not isinstance(v, dict):
            continue
        price = v.get("price")
        if price is None:
            continue
        try:
            price_dec = float(price) / 100.0
        except (TypeError, ValueError):
            continue
        v_title = (v.get("title") or "").strip()
        name = title if v_title in ("Default Title", "") else f"{title} ({v_title})"
        rows.append(
            {
                "product_id": str(v.get("sku") or v.get("id") or data.get("id") or ""),
                "product_name": name[:500],
                "category": category,
                "price": f"{price_dec:.2f}",
                "available": bool(v.get("available", True)),
                "url": (
                    f"{base_url}/products/{handle}?variant={v.get('id')}"
                    if base_url and handle
                    else None
                ),
            }
        )
    return rows or None


def _rows_from_analytics_meta(html: str, base_url: str):
    """Tier 2: window.ShopifyAnalytics `var meta = {"product": {...}}` blob."""
    m = _ANALYTICS_META_RE.search(html)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except (json.JSONDecodeError, ValueError):
        return None
    product = data.get("product") if isinstance(data, dict) else None
    if not isinstance(product, dict):
        return None
    variants = product.get("variants") or []
    if not variants:
        return None
    category = product.get("type") or None
    handle = product.get("handle") or ""
    rows = []
    for v in variants:
        if not isinstance(v, dict):
            continue
        price = v.get("price")
        if price is None:
            continue
        try:
            price_dec = float(price) / 100.0
        except (TypeError, ValueError):
            continue
        name = (v.get("name") or "").strip()
        if not name:
            continue
        rows.append(
            {
                "product_id": str(
                    v.get("sku") or v.get("id") or product.get("id") or ""
                ),
                "product_name": name[:500],
                "category": category,
                "price": f"{price_dec:.2f}",
                "available": True,
                "url": (
                    f"{base_url}/products/{handle}?variant={v.get('id')}"
                    if base_url and handle
                    else None
                ),
            }
        )
    return rows or None


def _rows_from_ld_json(html: str):
    """Tier 3: JSON-LD Product blocks, one offer per variant."""
    rows = []
    for m in _LDJSON_RE.finditer(html):
        try:
            data = json.loads(m.group(1).strip())
        except (json.JSONDecodeError, ValueError):
            continue
        for obj in data if isinstance(data, list) else [data]:
            if not isinstance(obj, dict) or obj.get("@type") != "Product":
                continue
            name = (obj.get("name") or "").strip()
            if not name:
                continue
            offers = obj.get("offers")
            if isinstance(offers, dict):
                offers = [offers]
            elif not isinstance(offers, list):
                offers = []
            for offer in offers:
                if not isinstance(offer, dict):
                    continue
                price = offer.get("price")
                if price is None:
                    continue
                try:
                    price_dec = float(price)
                except (TypeError, ValueError):
                    continue
                availability = str(offer.get("availability") or "").lower()
                rows.append(
                    {
                        "product_id": str(obj.get("sku") or obj.get("mpn") or ""),
                        "product_name": name[:500],
                        "category": obj.get("category") or None,
                        "price": f"{price_dec:.2f}",
                        "currency": offer.get("priceCurrency") or None,
                        "available": ("instock" in availability)
                        if availability
                        else True,
                        "url": offer.get("url") or None,
                    }
                )
    return rows or None


def _rows_from_og_meta(html: str):
    """Tier 4: OpenGraph price meta tags — last resort, single price only."""
    tags = {}
    for tag in _META_TAG_RE.findall(html):
        prop = _META_PROP_RE.search(tag)
        content = _META_CONTENT_RE.search(tag)
        if prop and content:
            tags[prop.group(1)] = content.group(1)
    title = tags.get("og:title")
    price = tags.get("og:price:amount") or tags.get("product:price:amount")
    if not title or not price:
        return None
    try:
        price_dec = float(price)
    except ValueError:
        return None
    currency = tags.get("og:price:currency") or tags.get("product:price:currency")
    return [
        {
            "product_name": title.strip()[:500],
            "price": f"{price_dec:.2f}",
            "currency": currency,
            "url": tags.get("og:url"),
        }
    ]


class ShopifyBaseSpider(scrapy.Spider):
    name = None
    base_url: str = ""
    currency: str = ""
    language: str = "en"
    PRODUCTS_PATH: str = "/products.json"

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
            f"{self.base_url}{self.PRODUCTS_PATH}?limit={PER_PAGE}&page=1",
            callback=self.parse_page,
            meta={"page": 1},
        )

    def parse_page(self, response):
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON response at {response.url}")
            return
        products = data.get("products") if isinstance(data, dict) else None
        if not products:
            return
        page = response.meta["page"]
        logger.info(f"{self.name} page={page} count={len(products)}")
        for p in products:
            for item in self._items(p):
                yield item
        if len(products) >= PER_PAGE and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{self.base_url}{self.PRODUCTS_PATH}?limit={PER_PAGE}&page={nxt}",
                callback=self.parse_page,
                meta={"page": nxt},
            )

    def _items(self, p: dict):
        title = (p.get("title") or "").strip()
        handle = p.get("handle") or ""
        category = p.get("product_type") or None
        variants = p.get("variants") or []
        if not (title and variants):
            return
        for v in variants:
            if not isinstance(v, dict):
                continue
            price = v.get("price")
            if not price:
                continue
            sku = v.get("sku") or v.get("id") or p.get("id")
            v_title = (v.get("title") or "").strip()
            name = title if v_title in ("Default Title", "") else f"{title} ({v_title})"
            yield {
                "product_id": str(sku),
                "product_name": name[:500],
                "category": category,
                "price": str(price),
                "currency": self.currency,
                "available": bool(v.get("available", True)),
                "url": f"{self.base_url}/products/{handle}?variant={v.get('id')}",
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

    @classmethod
    def parse_html(cls, html: str, url: str):
        """Parse one archived Shopify product-detail page into row dicts.

        Pure and stateless — used by the Wayback/CC backfiller to replay
        archived storefront HTML (a different surface than the live
        /products.json endpoint `_items()` reads). Tries the extraction
        tiers above in order of reliability; the first one that yields any
        rows wins. Does NOT stamp `scraped_at_utc` — the caller sets it to
        the snapshot time.
        """
        rows = (
            _rows_from_product_json(html, cls.base_url)
            or _rows_from_analytics_meta(html, cls.base_url)
            or _rows_from_ld_json(html)
            or _rows_from_og_meta(html)
        )
        if not rows:
            return
        for row in rows:
            if not row.get("url"):
                row["url"] = url
            if not row.get("currency"):
                row["currency"] = cls.currency
            row.setdefault("language", cls.language)
            yield row
