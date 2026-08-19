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
from urllib.parse import urljoin, urlsplit

_SCRIPT_OPEN_RE = re.compile(r"<script\b", re.IGNORECASE)
_SCRIPT_ATTR_RE = re.compile(r'\s*([\w:.-]+)(?:\s*=\s*(?:"([^"]*)"|\'([^\']*)\'))?')
_META_RE = re.compile(r"<meta\b[^>]*>", re.IGNORECASE)
_ATTR_RE = re.compile(r'(\w[\w:.-]*)\s*=\s*["\']([^"\']*)["\']')
_CURRENCY_RE = re.compile(r"^[A-Za-z]{3}$")


def _iter_script_tags(html_text: str) -> Iterator[tuple[dict[str, str], str]]:
    """Yield ``(attrs, body)`` for every ``<script>`` tag.

    A hand-rolled scanner rather than a ``[^>]*`` regex: some React/Nuxt
    themes (confirmed on billa.sk) put JSON-LD in a ``children="..."``
    attribute whose value legitimately contains an unescaped ``>`` (e.g. a
    category string ``"LEAFLET > KW 37/2026 > Inside"``) — a regex treating
    ``>`` as always closing the tag truncates the attribute value right
    there and drops the JSON-LD entirely.
    """
    n = len(html_text)
    pos = 0
    while True:
        m = _SCRIPT_OPEN_RE.search(html_text, pos)
        if not m:
            return
        i = m.end()
        attrs: dict[str, str] = {}
        while i < n and html_text[i] != ">":
            am = _SCRIPT_ATTR_RE.match(html_text, i)
            if not am or am.end() == i:
                i += 1
                continue
            name, dq, sq = am.groups()
            attrs[name.lower()] = (
                dq if dq is not None else (sq if sq is not None else "")
            )
            i = am.end()
        if i >= n:
            return
        body_start = i + 1
        close = html_text.find("</script>", body_start)
        if close == -1:
            return
        yield attrs, html_text[body_start:close]
        pos = close + len("</script>")


def _valid_currency(code: Any) -> str | None:
    """Reject junk `priceCurrency`/meta values that aren't a 3-letter code.

    Some sites (4sough.com confirmed) ship a literal descriptive string —
    e.g. ``"Afghanistan fiat currency"`` — in the currency meta tag instead
    of an ISO code. Passing that through would silently corrupt the
    `currency` column downstream.
    """
    if not code:
        return None
    code = str(code).strip()
    return code.upper() if _CURRENCY_RE.match(code) else None


def _same_page(row_url: str, page_url: str) -> bool:
    """Compare scheme+host+path only — query strings/fragments legitimately vary."""
    a, b = urlsplit(row_url), urlsplit(page_url)
    return (a.netloc, a.path.rstrip("/")) == (b.netloc, b.path.rstrip("/"))


def _dedupe_product_rows(rows: list[dict], page_url: str) -> list[dict]:
    """Collapse same-SKU price duplicates and drop off-page recommendation rails.

    A multi-offer Product node emits one row per offer, which doubles up when
    a site lists both a list price and a promo price for the same SKU
    (confirmed on sodimac.com.pe, falabella.com.co) — keep only the cheapest
    offer per (name, sku). Keying on the sku as well as the name preserves
    genuine multi-variant products, whose offers share a name but differ by
    sku; collapsing those to the cheapest would silently drop the dearer
    variants for the 17+ spiders already calling this. Some listing/detail pages also embed several
    unrelated Product nodes as a "similar items" rail (confirmed on
    pakwheels.com) rather than the single item the URL is for — once more
    than one distinct product name is present, keep only the row(s) whose url
    matches the page url, falling back to the first row if none match,
    instead of writing every recommendation as a historical price point.
    """
    by_sku: dict[tuple, list[dict]] = {}
    for row in rows:
        by_sku.setdefault((row["product_name"], row.get("product_id")), []).append(row)
    collapsed = [
        min(group, key=lambda r: float(r["price"])) for group in by_sku.values()
    ]
    if len(collapsed) <= 1:
        return collapsed
    on_page = [r for r in collapsed if _same_page(r["url"], page_url)]
    return on_page or collapsed[:1]


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
    """Every JSON-LD object in the page, flattening ``@graph`` and arrays.

    Most themes put the JSON in the ``<script type="application/ld+json">``
    body, but some React/Nuxt themes (confirmed on billa.sk) instead render
    it into a ``children="..."`` attribute on an otherwise-empty script tag,
    HTML-entity-escaped (``&quot;`` for every ``"``) because it went through
    a JSX/Vue attribute serializer rather than being written as page markup.
    Both surfaces are checked; body wins when a tag somehow has both.
    """

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

    for attrs, body in _iter_script_tags(html_text):
        if attrs.get("type", "").lower() != "application/ld+json":
            continue
        raw = body.strip() or _html.unescape(attrs.get("children", "")).strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
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
    if price is None:
        # Some AggregateOffer nodes carry lowPrice/highPrice directly with no
        # nested `offers` list (schema.org allows this) -- e.g. 4sough_af.
        price = offer.get("lowPrice")
    return price


def rows_from_jsonld(html_text: str, url: str) -> list[dict]:
    """Price rows from every schema.org Product node in the page.

    One row per distinct product name -- see `_dedupe_product_rows` for how
    multi-offer and multi-node pages are collapsed.
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
                "url": urljoin(url, offer.get("url") or node.get("url") or url),
            }
            sku = offer.get("sku") or node.get("sku") or node.get("productID")
            if sku:
                row["product_id"] = str(sku)
            currency = _valid_currency(
                offer.get("priceCurrency") or node.get("priceCurrency")
            )
            if currency:
                row["currency"] = currency
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
    return _dedupe_product_rows(rows, url)


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
        "url": urljoin(url, meta.get("og:url") or url),
    }
    currency = _valid_currency(
        meta.get("product:price:currency") or meta.get("og:price:currency")
    )
    if currency:
        row["currency"] = currency
    avail = meta.get("product:availability") or meta.get("og:availability")
    if avail:
        row["available"] = "out" not in avail.lower()
    return row
