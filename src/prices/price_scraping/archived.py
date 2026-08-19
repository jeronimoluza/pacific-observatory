"""Generic extractors for archived product-detail HTML.

Platform spiders scrape JSON APIs; the pages Common Crawl and Wayback hold are
the *storefront* HTML those APIs sit behind. Replaying that HTML into price
rows needs a different parser, exposed per-spider as a ``parse_html(html, url)``
classmethod (see ``prices.backfill._load_spider_parse_html``).

Most storefronts, whatever the platform, embed the same two portable surfaces —
schema.org JSON-LD and OpenGraph meta. Those live here so each platform base
only has to implement what is genuinely platform-specific (Shopify's variant
blob, VTEX's Apollo cache, Woo's theme DOM) and falls back to shared code for
the rest.

Rows returned here omit ``scraped_at_utc`` on purpose: the caller stamps it
with the *snapshot* time. A parser that stamps ``now()`` silently collapses a
historical series into a single date.
"""

from __future__ import annotations

import html as _html
import json
import re
from typing import Any, Iterator

_LDJSON_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)
_META_RE = re.compile(r"<meta\b[^>]*>", re.IGNORECASE)
_ATTR_RE = re.compile(r'(\w[\w:.-]*)\s*=\s*["\']([^"\']*)["\']')


def normalize_price(raw: Any) -> str | None:
    """Strip currency symbols and thousands separators.

    Resolves the EU (``1.234,56``) vs US (``1,234.56``) decimal convention by
    which separator appears last. A lone comma is a decimal point only when
    exactly two digits follow it — ``1,50`` is one-fifty, ``1,500`` is fifteen
    hundred.
    """
    if raw is None:
        return None
    s = re.sub(r"[^\d.,\-]", "", str(raw))
    if not s:
        return None
    has_comma, has_dot = "," in s, "." in s
    if has_comma and has_dot:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif has_comma:
        tail = s.split(",")[-1]
        s = s.replace(",", ".") if len(tail) == 2 else s.replace(",", "")
    try:
        return str(float(s))
    except ValueError:
        return None


def iter_jsonld_nodes(html_text: str) -> Iterator[dict]:
    """Every JSON-LD object in the page, flattening ``@graph`` and arrays."""

    def walk(data):
        if isinstance(data, list):
            for item in data:
                yield from walk(item)
        elif isinstance(data, dict):
            yield data
            graph = data.get("@graph")
            if isinstance(graph, list):
                for item in graph:
                    yield from walk(item)

    for block in _LDJSON_RE.findall(html_text):
        try:
            data = json.loads(block.strip())
        except (json.JSONDecodeError, ValueError):
            continue
        yield from walk(data)


def _is_product(node: dict) -> bool:
    t = node.get("@type")
    if isinstance(t, list):
        return any(str(x).lower() == "product" for x in t)
    return str(t).lower() == "product"


def _offer_list(node: dict) -> list[dict]:
    offers = node.get("offers")
    if isinstance(offers, dict):
        # AggregateOffer wraps the real per-variant offers.
        inner = offers.get("offers")
        if isinstance(inner, list):
            return [o for o in inner if isinstance(o, dict)]
        return [offers]
    if isinstance(offers, list):
        return [o for o in offers if isinstance(o, dict)]
    return []


def _price_of(offer: dict) -> Any:
    price = offer.get("price")
    if price is None:
        spec = offer.get("priceSpecification")
        if isinstance(spec, dict):
            price = spec.get("price")
        elif isinstance(spec, list) and spec:
            price = (spec[0] or {}).get("price")
    return price


def rows_from_jsonld(html_text: str, url: str) -> list[dict]:
    """Price rows from every schema.org Product node in the page.

    One row per offer, so multi-variant products yield several rows.
    """
    rows: list[dict] = []
    for node in iter_jsonld_nodes(html_text):
        if not _is_product(node):
            continue
        name = node.get("name")
        if not name:
            continue
        category = node.get("category")
        if isinstance(category, dict):
            category = category.get("name")
        for offer in _offer_list(node):
            price = normalize_price(_price_of(offer))
            if not price or float(price) <= 0:
                continue
            row = {
                "product_name": _html.unescape(str(name)).strip()[:500],
                "price": price,
                "url": offer.get("url") or node.get("url") or url,
            }
            sku = offer.get("sku") or node.get("sku") or node.get("productID")
            if sku:
                row["product_id"] = str(sku)
            currency = offer.get("priceCurrency") or node.get("priceCurrency")
            if currency:
                row["currency"] = str(currency)
            if category:
                row["category"] = str(category)
            availability = offer.get("availability")
            if availability:
                low = str(availability).lower()
                if "outofstock" in low or "soldout" in low or "discontinued" in low:
                    row["available"] = False
                elif "instock" in low or "limitedavailability" in low:
                    row["available"] = True
            rows.append(row)
    return rows


def meta_tags(html_text: str) -> dict[str, str]:
    """``{property-or-name: content}`` for every meta tag in the page."""
    out: dict[str, str] = {}
    for tag in _META_RE.findall(html_text):
        attrs = dict(_ATTR_RE.findall(tag))
        key = attrs.get("property") or attrs.get("name") or attrs.get("itemprop")
        content = attrs.get("content")
        if key and content:
            out.setdefault(key.lower(), content)
    return out


def row_from_meta(html_text: str, url: str) -> dict | None:
    """Last-resort row from OpenGraph / ``product:price:*`` meta tags.

    Takes the first candidate that resolves to a **non-zero** price. Some
    storefronts ship a stale ``product:price:amount="0"`` alongside correct
    ``itemprop`` microdata; a plain ``or`` chain would let the zero win and
    silently write a 0.00 into the series.
    """
    meta = meta_tags(html_text)
    price = None
    for key in ("product:price:amount", "og:price:amount", "price"):
        candidate = normalize_price(meta.get(key))
        if candidate and float(candidate) > 0:
            price = candidate
            break
    name = meta.get("og:title") or meta.get("twitter:title")
    if not (price and name):
        return None
    row = {
        "product_name": _html.unescape(name).strip()[:500],
        "price": price,
        "url": meta.get("og:url") or url,
    }
    currency = meta.get("product:price:currency") or meta.get("og:price:currency")
    if currency:
        row["currency"] = currency
    avail = meta.get("product:availability") or meta.get("og:availability")
    if avail:
        row["available"] = "out" not in avail.lower()
    return row
