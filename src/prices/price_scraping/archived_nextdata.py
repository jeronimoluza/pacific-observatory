"""Product rows from a Next.js Pages Router hydration blob.

Sibling to `archived_embedded.py`, which reads the App Router's streaming
"flight" protocol (`self.__next_f.push(...)`). This reads the older, static
form: a single JSON document in `<script id="__NEXT_DATA__">`. The two are
the same idea in different wrappers, but the older one is far more common in
the archive -- across 3,415 cached captures spanning ~30 sources,
`__NEXT_DATA__` appears on 4.6% and `self.__next_f` on 0.6%. Every one of
those pages was being banked as a miss.

Because the blob is a parsed JSON document rather than a concatenated text
stream, this walks the object tree directly instead of brace-matching text.
What it looks for is the same thing the flight tier looks for, and for the
same reason: a hydration payload has no shared schema across sites, so the
only portable signal is an object that carries *both* a name-like and a
price-like field. The paths differ per source and per era -- confirmed
`.props.pageProps.product` on kurly.com and prisma.fi,
`.query.data.mainContent.records[].allMeta` on liverpool.com.mx,
`.props.pageProps.pageData.items[]` on drogasil.com.br -- so keying on a path
would need a registry that goes stale every time a site rebuilds.

Rows returned here, like `archived.py`, omit `scraped_at_utc` -- the caller
stamps the snapshot time.
"""

from __future__ import annotations

import json
import re
from typing import Any

import lxml.etree
import lxml.html

from .archived import _dedupe_product_rows, _valid_currency, normalize_price
from .archived_embedded import _url_id_candidates

_BLOB_RE = re.compile(
    r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL
)

_NAME_KEYS = ("name", "title", "productName", "product_name", "displayName")

# Every key here has to *name* a price. An earlier revision also accepted bare
# `value` and `amount`, which are the generic field names a payload uses for
# anything at all: it banked "Size (g)" at 100.0 and "Alto" at 40.0 -- product
# specification attributes -- with a perfectly clean-looking score. A price key
# that could equally hold a shoe width is not a price key.
_PRICE_KEYS = (
    "price", "salePrice", "sellingPrice", "finalPrice", "listPrice",
    "currentPrice", "promoPrice", "discountedPrice", "specialPrice",
    "minimumPromoPrice", "minimumListPrice", "priceValue", "unitPrice",
)
# Inside one of the keys above, the meaning is already established by the outer
# key, so a generic inner name is safe: {"price": {"value": 12.30}}.
_NESTED_PRICE_KEYS = ("value", "amount", "current", "gross", "centAmount")

_CURRENCY_KEYS = ("currency", "priceCurrency", "currencyCode")

# Objects reached through one of these keys are other products being advertised
# alongside this page's own -- confirmed on agrofy.com.ar, whose payload carries
# 11 cars under `merchantRelatedProducts.Hits[]`. Attributing them to this URL
# would write a series that changes whenever the rail rotates.
_RAIL_RE = re.compile(
    r"related|recommend|similar|crosssell|upsell|alsobought|alsoviewed"
    r"|youmaylike|suggest|carousel",
    re.IGNORECASE,
)

# A payload key name reaching this module as a "product name": `cfs_pt`,
# `scheduledEnabled`. Real product names are prose, not identifiers.
_IDENTIFIER_RE = re.compile(r"^[a-z][A-Za-z0-9_]*$")

_MAX_DEPTH = 14
_MAX_LIST = 200


def _to_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip().replace(",", "")
        if re.fullmatch(r"\d+(?:\.\d+)?", text):
            return float(text)
    return None


def _find_name(obj: dict) -> str | None:
    for key in _NAME_KEYS:
        value = obj.get(key)
        if not isinstance(value, str):
            continue
        name = value.strip()
        if name and not _IDENTIFIER_RE.fullmatch(name):
            return name
    return None


def _find_price(obj: dict) -> float | None:
    for key in _PRICE_KEYS:
        if key not in obj:
            continue
        number = _to_number(obj[key])
        if number and number > 0:
            return number
        nested = obj[key]
        if isinstance(nested, dict):
            for inner in _NESTED_PRICE_KEYS:
                number = _to_number(nested.get(inner))
                if number and number > 0:
                    return number
    return None


def _find_currency(obj: dict) -> str | None:
    for key in _CURRENCY_KEYS:
        code = _valid_currency(obj.get(key))
        if code:
            return code
    return None


def _find_id(obj: dict) -> str | None:
    for key in ("sku", "productId", "id", "_id", "code"):
        value = obj.get(key)
        if isinstance(value, (str, int)) and str(value).strip():
            return str(value)
    return None


def _walk(node: Any, out: list, depth: int = 0) -> None:
    """Every product-shaped object in the tree, skipping recommendation rails."""
    if depth > _MAX_DEPTH:
        return
    if isinstance(node, dict):
        name = _find_name(node)
        price = _find_price(node)
        if name and price:
            out.append((name, price, _find_currency(node), _find_id(node)))
        for key, value in node.items():
            if _RAIL_RE.search(key):
                continue
            _walk(value, out, depth + 1)
    elif isinstance(node, list):
        for value in node[:_MAX_LIST]:
            _walk(value, out, depth + 1)


# A number the page renders *as money*: next to a currency symbol or a
# three-letter code. The first version of this guard compared against every
# number in the text, which let a payload price corroborate itself against an
# unrelated date or item count, and admitted both separator readings of the
# same token so that `20,00` counted as 2000 as well as 20.00 -- exactly the
# value the guard exists to reject.
_SYMBOLS = r"\$|€|£|¥|₩|₫|₺|₽|₴|₸|﷼|zł|Kč|лв|ден|R\$|US\$|MX\$"
_MONEY_RE = re.compile(
    r"(?:(?:%s|\b[A-Z]{3})\s*(\d[\d.,]*)|(\d[\d.,]*)\s*(?:%s|\b[A-Z]{3}\b))"
    % (_SYMBOLS, _SYMBOLS)
)


def _parse_money(token: str) -> set[float]:
    """The value(s) a rendered money token can mean.

    Separator conventions are not knowable from the token alone, but they are
    not a free-for-all either: a separator followed by exactly two digits is a
    decimal point, and one followed by exactly three is a thousands mark. Only
    a lone `1.199`-shaped token is genuinely ambiguous, and only there are both
    readings returned.
    """
    token = token.strip().rstrip(".,")
    if re.fullmatch(r"\d+", token):
        return {float(token)}
    # A lone `1.199` is the one genuinely ambiguous shape -- 1199 under a
    # thousands convention, 1.199 under a decimal one -- so both readings are
    # returned and the caller matches against either.
    if re.fullmatch(r"\d{1,3}[.,]\d{3}", token):
        return {float(re.sub(r"[.,]", "", token)),
                float(token.replace(",", "."))}
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", token):
        return {float(re.sub(r"[.,]", "", token))}
    # Groups are matched rather than sliced by offset: an earlier revision
    # assumed the decimal part was always two digits and turned `6.6` into
    # the string `..6`, which raised out of the tier and stopped the driver.
    match = re.fullmatch(r"(\d{1,3}(?:[.,]\d{3})*)[.,](\d{1,2})", token)
    if match:
        return {float(re.sub(r"[.,]", "", match.group(1)) + "." + match.group(2))}
    return set()


def _visible_prices(html_text: str) -> set[float]:
    """Every value the page renders as money.

    The blob is a machine surface and states its prices in whatever unit the
    site's backend happens to use. prisma.fi publishes `finalPrice: 2000` for a
    book the page displays as `20,00 EUR` -- minor units. Banking that as-is is
    a 100x error on every row of that shape, and nothing inside the payload
    distinguishes it from liverpool.com.mx's `minimumPromoPrice: '7939'`, which
    really is 7,939 pesos. What the page *shows* is the only available arbiter,
    so it is consulted wherever the page shows anything at all.
    """
    try:
        text = lxml.html.fromstring(html_text).text_content() or ""
    except (ValueError, lxml.etree.ParserError):
        return set()
    out = set()
    for before, after in _MONEY_RE.findall(text):
        out |= _parse_money(before or after)
    return out


def _page_scale(prices: list[float], shown: set[float]) -> float:
    """1 or 100 -- the divisor that reconciles this payload with the page.

    Deciding this per page rather than per row is what keeps the check honest.
    prisma.fi renders `20,00 EUR` for a `finalPrice` of 2000, so every price in
    that payload is in cents and dividing one but not another would be
    incoherent. liverpool.com.mx renders no product price at all, so nothing
    argues for rescaling and the payload stands as written.
    """
    if not shown:
        return 1.0
    matches = {}
    for scale in (1.0, 100.0):
        matches[scale] = sum(
            1 for price in prices
            if any(abs(price / scale - number) < 0.01 for number in shown)
        )
    return 100.0 if matches[100.0] > matches[1.0] else 1.0


def extract_nextdata_candidates(html_text: str) -> list[tuple[dict, set[str]]]:
    """``(row, id_candidates)`` for every product-shaped object in the blob."""
    match = _BLOB_RE.search(html_text)
    if not match:
        return []
    try:
        data = json.loads(match.group(1))
    except (json.JSONDecodeError, ValueError):
        return []
    found: list = []
    _walk(data, found)
    if not found:
        return []
    scale = _page_scale([price for _n, price, _c, _i in found],
                        _visible_prices(html_text))
    out = []
    for name, price, currency, product_id in found:
        normalized = normalize_price(price / scale, currency)
        if not normalized or float(normalized) <= 0:
            continue
        row = {"product_name": name[:500], "price": normalized}
        if product_id:
            row["product_id"] = product_id
        if currency:
            row["currency"] = currency
        out.append((row, {product_id} if product_id else set()))
    return out


def rows_from_nextdata(html_text: str, url: str) -> list[dict]:
    """Price rows from a Next.js Pages Router `__NEXT_DATA__` blob.

    Attribution follows `rows_from_next_flight` exactly, and for the same
    reason: one product URL's payload routinely embeds other products, so where
    an extracted object's id matches a token in the URL itself, only that match
    is kept. A page with no URL/id correlation at all is more likely a genuine
    listing -- confirmed on drogasil.com.br, whose payload carries the 24
    products the page actually lists -- so there every row is returned.
    """
    candidates = extract_nextdata_candidates(html_text)
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
