"""Why does a page with an application/ld+json script yield no row?

The autopsy found 4,634 misses (36.8%) that carry a JSON-LD script the
shipped `rows_from_jsonld` produced nothing from. This attributes each one to
a specific rejection point and tests candidate widenings against it, offline,
on the archived miss HTML.
"""
import html as _html
import json
import re
import sys

sys.path.insert(0, "/tmp/parse")
from archived import _iter_script_tags, normalize_price  # noqa: E402

LD = "application/ld+json"


# ---------------------------------------------------------------- raw surface

def ld_blobs(html_text):
    """(raw_text, source) for every ld+json script, body or children attr."""
    out = []
    for attrs, body in _iter_script_tags(html_text):
        if attrs.get("type", "").lower() != LD:
            continue
        raw = body.strip()
        src = "body"
        if not raw:
            raw = _html.unescape(attrs.get("children", "")).strip()
            src = "children"
        if raw:
            out.append((raw, src))
    return out


# ------------------------------------------------------------- JSON repair W5

_CDATA = re.compile(r"^\s*(?://)?\s*<!\[CDATA\[(.*?)\]\]>\s*$", re.DOTALL)
_HTML_COMMENT = re.compile(r"^\s*<!--(.*?)-->\s*$", re.DOTALL)
_TRAILING_COMMA = re.compile(r",(\s*[}\]])")
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def repair(raw):
    """Best-effort fixes for the malformations storefronts actually ship."""
    s = raw
    m = _CDATA.match(s) or _HTML_COMMENT.match(s)
    if m:
        s = m.group(1)
    s = _CTRL.sub("", s)
    s = _TRAILING_COMMA.sub(r"\1", s)
    return s


def parse_any(raw):
    """(data, how) - strict, repaired, or entity-unescaped."""
    try:
        return json.loads(raw), "strict"
    except Exception:
        pass
    try:
        return json.loads(repair(raw)), "repaired"
    except Exception:
        pass
    if "&quot;" in raw or "&amp;" in raw:
        try:
            return json.loads(repair(_html.unescape(raw))), "unescaped"
        except Exception:
            pass
    try:
        s = repair(raw).replace("\n", " ").replace("\r", " ")
        return json.loads(s), "flattened"
    except Exception:
        return None, "unparseable"


# --------------------------------------------------------------- node walking

def walk_shipped(data):
    """Exactly what iter_jsonld_nodes does: top level + @graph only."""
    if isinstance(data, list):
        for it in data:
            yield from walk_shipped(it)
    elif isinstance(data, dict):
        yield data
        g = data.get("@graph")
        if isinstance(g, list):
            for it in g:
                yield from walk_shipped(it)


_SKIP_KEYS = {"@context"}


def walk_deep(data, depth=0):
    """W1: recurse into every nested dict/list, not just @graph."""
    if depth > 12:
        return
    if isinstance(data, list):
        for it in data:
            yield from walk_deep(it, depth + 1)
    elif isinstance(data, dict):
        yield data
        for k, v in data.items():
            if k in _SKIP_KEYS:
                continue
            if isinstance(v, (dict, list)):
                yield from walk_deep(v, depth + 1)


def type_of(node):
    t = node.get("@type")
    if isinstance(t, list):
        return [str(x).rsplit("/", 1)[-1].lower() for x in t]
    if t is None:
        return []
    return [str(t).rsplit("/", 1)[-1].lower()]


SHIPPED_PRODUCT = {"product"}
# W2: types that carry a real retail price in practice
WIDE_PRODUCT = SHIPPED_PRODUCT | {
    "productgroup", "individualproduct", "productmodel", "vehicle", "car",
    "book", "softwareapplication", "mobileapplication", "videogame", "movie",
    "musicalbum", "menuitem", "hotelroom", "trip", "event", "course",
    "service", "creativework", "imageobject", "tvseries", "apartment",
    "house", "singlefamilyresidence", "realestatelisting",
}


def is_product(node, types):
    return any(t in types for t in type_of(node))


# --------------------------------------------------------------- price/name

def offers_of(node):
    o = node.get("offers")
    if isinstance(o, dict):
        inner = o.get("offers")
        if isinstance(inner, list):
            return [x for x in inner if isinstance(x, dict)]
        return [o]
    if isinstance(o, list):
        return [x for x in o if isinstance(x, dict)]
    return []


def price_shipped(offer):
    p = offer.get("price")
    if p is None:
        spec = offer.get("priceSpecification")
        if isinstance(spec, dict):
            p = spec.get("price")
        elif isinstance(spec, list) and spec:
            p = (spec[0] or {}).get("price")
    if p is None:
        p = offer.get("lowPrice")
    return p


def price_wide(d):
    """W3: any price-bearing field, on an offer OR straight on the node."""
    for k in ("price", "lowPrice", "highPrice", "priceValue"):
        v = d.get(k)
        if v not in (None, "", []):
            return v
    spec = d.get("priceSpecification")
    if isinstance(spec, list):
        spec = spec[0] if spec else None
    if isinstance(spec, dict):
        for k in ("price", "lowPrice", "minPrice"):
            v = spec.get(k)
            if v not in (None, "", []):
                return v
    return None


def positive(p):
    n = normalize_price(p)
    try:
        return n if n and float(n) > 0 else None
    except (TypeError, ValueError):
        return None


_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_OG = re.compile(
    r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)',
    re.IGNORECASE)
_H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)
_TAGS = re.compile(r"<[^>]+>")


def page_name(html_text):
    """W6: name fallback when the Product node has a price but no name."""
    for rx in (_OG, _H1, _TITLE):
        m = rx.search(html_text)
        if m:
            t = _html.unescape(_TAGS.sub(" ", m.group(1))).strip()
            t = re.sub(r"\s+", " ", t)
            if 2 < len(t) < 300:
                return t
    return None


def node_name(node):
    n = node.get("name")
    if isinstance(n, dict):
        for v in n.values():
            if isinstance(v, str) and v.strip():
                n = v
                break
    if isinstance(n, list) and n:
        n = n[0]
    if isinstance(n, str) and n.strip():
        return _html.unescape(n).strip()[:500]
    for k in ("title", "headline"):
        v = node.get(k)
        if isinstance(v, str) and v.strip():
            return _html.unescape(v).strip()[:500]
    return None
