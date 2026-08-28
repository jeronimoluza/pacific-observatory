"""Product rows embedded in a JS-framework hydration payload.

Sibling to `archived.py` (schema.org JSON-LD / OpenGraph meta) for the next
tier of the archived-HTML fallback chain: pages where the product data was
server-rendered straight into a framework's own hydration stream instead of
into any portable markup surface. Currently one mechanism is implemented:
Next.js App Router's React Server Components "flight" protocol, i.e. a
series of `self.__next_f.push([1, "<chunk>"])` script tags.

Rows returned here, like `archived.py`, omit `scraped_at_utc` -- the caller
stamps the snapshot time.
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import parse_qs, urlsplit

from .archived import _dedupe_product_rows, _valid_currency, normalize_price

_FLIGHT_CHUNK_RE = re.compile(r'self\.__next_f\.push\(\[1,(".*?")\]\)', re.DOTALL)
_OBJECT_ANCHOR_RE = re.compile(r'\{"(?:id|_id|productId)":(?:"[^"]*"|-?\d+),"')

_NAME_KEYS = ("name", "title", "productName", "product_name")
_PRICE_KEYS = ("includingTaxPrice", "price", "sellingPrice", "salePrice")
_PRICE_GROUP_KEYS = ("prices",)
# barcode/janCode before sku/productId/id: onmart.mn (confirmed) overloads its
# "sku" field with a free-text variant descriptor ("75мл | ...эмчилэх") rather
# than an identifier, so a naive first-populated-wins order picks that
# descriptor as the product_id instead of the real barcode.
_ID_KEYS = ("barcode", "janCode", "productId", "sku", "id", "_id")
_SENTINEL = "$undefined"


def _flight_blob(html_text: str) -> str:
    """Concatenated, JSON-string-unescaped text of every flight chunk."""
    parts = []
    for raw in _FLIGHT_CHUNK_RE.findall(html_text):
        try:
            parts.append(json.loads(raw))
        except (json.JSONDecodeError, ValueError):
            continue
    return "".join(parts)


def _balanced_objects(text: str, anchor_re: "re.Pattern[str]") -> list[str]:
    """Every `{...}` substring starting at an anchor match, brace-balanced
    with quote-awareness so braces inside JSON string values don't count."""
    out = []
    seen_starts = set()
    for m in anchor_re.finditer(text):
        start = m.start()
        if start in seen_starts:
            continue
        seen_starts.add(start)
        depth = 0
        in_str = False
        esc = False
        end = None
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
        if end:
            out.append(text[start:end])
    return out


def _first_str(value: Any) -> str | None:
    """A field's display string -- straight through, or the first populated
    value of a locale dict (e.g. `{"en": "..."}`, confirmed on onmart.mn)."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for v in value.values():
            if isinstance(v, str) and v.strip() and v != _SENTINEL:
                return v
    return None


def _find_name(obj: dict) -> str | None:
    for key in _NAME_KEYS:
        if key in obj:
            v = _first_str(obj[key])
            if v and v.strip():
                return v.strip()
    return None


def _find_price(obj: dict) -> Any:
    for key in _PRICE_KEYS:
        v = obj.get(key)
        if isinstance(v, (int, float, str)) and v != _SENTINEL:
            return v
    for key in _PRICE_GROUP_KEYS:
        group = obj.get(key)
        if isinstance(group, dict):
            for pkey in ("price", "originalPrice", "sellingPrice"):
                v = group.get(pkey)
                if isinstance(v, (int, float, str)) and v != _SENTINEL:
                    return v
    return None


def _find_id(obj: dict) -> str | None:
    for key in _ID_KEYS:
        v = obj.get(key)
        if v and v != _SENTINEL:
            return str(v)
    return None


def _url_id_candidates(url: str) -> set[str]:
    """Every plausible product-id token embedded in a URL: the last path
    segment plus every query-param value (`?productId=...`, `?variant=...`,
    ...) -- the vocabulary for those varies per site, so this takes them all
    rather than guessing a key name."""
    parsed = urlsplit(url)
    ids = {v for values in parse_qs(parsed.query).values() for v in values}
    tail = parsed.path.rstrip("/").rsplit("/", 1)[-1]
    if tail:
        ids.add(tail)
    return ids


def extract_flight_candidates(html_text: str) -> list[tuple[dict, set[str]]]:
    """``(row, id_candidates)`` for every product-shaped object in a Next.js
    flight payload, unfiltered and undeduplicated -- the low-level building
    block `rows_from_next_flight` narrows, and that a spider with its own
    per-page semantics (e.g. aeon_foodstyle_jp, whose archived article page
    legitimately lists ~20 distinct products) can use directly.

    An object counts as product-shaped if it carries *both* a name-like and
    a price-like field (checked against a priority list of the field names
    seen so far -- `name`/`title`, `price`/`includingTaxPrice`/nested
    `prices.price`); that compound check is the only thing that generalizes
    across sites, since flight payloads are an internal framework artifact
    with no shared schema (confirmed different field names between
    aeonfoodstyle.netsuper.aeon.com and onmart.mn). Unrelated flight-payload
    objects -- i18n strings, nav menus, GraphQL layout components, SVG
    clip-path defs -- fail the check and are silently skipped; confirmed on
    setec.mk, which uses this same flight protocol on a page whose product
    data is fetched client-side and so isn't in the payload at all.
    """
    blob = _flight_blob(html_text)
    if not blob:
        return []
    out = []
    for obj_text in _balanced_objects(blob, _OBJECT_ANCHOR_RE):
        try:
            obj = json.loads(obj_text)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(obj, dict):
            continue
        name = _find_name(obj)
        if not name:
            continue
        currency = _valid_currency(obj.get("currency") or obj.get("priceCurrency"))
        price = normalize_price(_find_price(obj), currency)
        if not price or float(price) <= 0:
            continue
        row = {"product_name": name[:500], "price": price}
        pid = _find_id(obj)
        if pid:
            row["product_id"] = pid
        if currency:
            row["currency"] = currency
        ids = {str(obj[k]) for k in _ID_KEYS if obj.get(k) not in (None, "", _SENTINEL)}
        out.append((row, ids))
    return out


def rows_from_next_flight(html_text: str, url: str) -> list[dict]:
    """Price rows from a Next.js App Router "flight" hydration payload --
    the generic fallback-chain tier for spiders with no `parse_html` hook.

    A single product-detail URL's flight payload can embed other products
    too (a "related items" rail, confirmed on onmart.mn: ~30 unrelated
    objects alongside the page's own product). Attributing all of them to
    this URL would corrupt that URL's historical series the next time the
    rail rotates to different items. When one of the extracted objects'
    id-like fields matches a token from the URL itself (a path segment or
    query value), only that match is kept; otherwise every extracted row is
    returned, since a page with no URL/id correlation at all is more likely
    a genuine multi-product listing (see `extract_flight_candidates`).
    """
    candidates = extract_flight_candidates(html_text)
    if not candidates:
        return []
    rows = [dict(row, url=url) for row, _ids in candidates]
    if len(rows) == 1:
        return rows
    target_ids = _url_id_candidates(url)
    if target_ids:
        matched = [dict(row, url=url) for row, ids in candidates if ids & target_ids]
        if matched:
            return _dedupe_product_rows(matched, url)
    return _dedupe_product_rows(rows, url)
