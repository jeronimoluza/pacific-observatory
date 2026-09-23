"""The one parser ladder for archived HTML: Common Crawl, local and fleet.

There used to be two. The local fetcher (``cc_warc_fetcher``) ran the spider's
``parse_html`` hook, then its CSS selectors, then four portable tiers; the EC2
fleet (``infra/fetch/ccfetch.py``) ran six portable tiers and no spider code.
The same capture could bank a row on one and nothing on the other, and every
fix had to be made twice. This module is both of them, in one order:

    hook -> selectors -> jsonld -> meta -> flight -> microdata -> nextdata -> bysource

Append-only: each tier runs only on a page every tier above it failed, so
adding a tier can never change a page that parses today.

Hooks are the one tier the fleet does not run. They live on scrapy spider
classes, and shipping them means shipping scrapy, twisted, pydantic and the
spider tree (~60 MB) to reach 0.4% of records. The fleet calls this with
``hook=None``; a source that parses only through its hook needs a local pass.

Stdlib, lxml and bs4 only, and flat imports at line start, so
``infra/fetch/bundle_parse.py`` can ship it.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from bs4 import BeautifulSoup

from .archived import row_from_meta, rows_from_jsonld
from .archived_bysource import rows_from_source
from .archived_embedded import rows_from_next_flight
from .archived_microdata import rows_from_microdata
from .archived_nextdata import rows_from_nextdata
from .selectors import SPIDER_SELECTORS, extract_with_fallback

logger = logging.getLogger(__name__)

_CHARSET = re.compile(rb"charset\s*=\s*[\"']?([\w\-]+)", re.I)

# Spiders that embed product data in ld+json rather than CSS-accessible elements.
_LDJSON_SPIDERS = {"cosmed", "fairprice", "carrefour_tw"}

# Spiders that embed price/name in __NEXT_DATA__ JSON (Next.js SPA, no meta price tag).
_NEXTDATA_SPIDERS = {"tiki"}


def decode(headers: Optional[bytes], body: bytes) -> str:
    """Text, preferring the charset the page declares.

    Old captures are routinely Shift_JIS, Big5, EUC-KR or windows-1251. Decoding
    those as latin-1 does not raise -- it silently produces mojibake, which
    reaches the product name and is unrecoverable downstream.
    """
    m = _CHARSET.search(headers or b"") or _CHARSET.search(body[:4096])
    if m:
        cs = m.group(1).decode("ascii", "ignore").lower()
        if cs.replace("_", "-") not in ("utf-8", "utf8"):
            try:
                return body.decode(cs)
            except (UnicodeDecodeError, LookupError):
                pass
    for enc in ("utf-8", "latin-1"):
        try:
            return body.decode(enc)
        except UnicodeDecodeError:
            continue
    return body.decode("utf-8", "replace")


def _ldjson_fallback(html: str, out: Dict[str, Any]) -> None:
    m = re.search(
        r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    if not m:
        return
    raw = m.group(1).strip()
    d = None
    for candidate in (raw, raw.rstrip().rstrip("}")):
        try:
            d = json.loads(candidate)
            break
        except Exception:
            continue
    if d is None:
        return
    if d.get("@type") != "Product":
        return
    if "product_name" not in out:
        name = d.get("name", "")
        if name:
            out["product_name"] = name
    if "price" not in out:
        offers = d.get("offers", {})
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        price = offers.get("price")
        if price is not None:
            out["price"] = str(price)
    if "category" not in out:
        cat_m = re.search(r'"ShopCategory_ShowName"\s*:\s*"([^"]+)"', html)
        if cat_m:
            out["category"] = cat_m.group(1)


def _nextdata_fallback(soup: BeautifulSoup, out: Dict[str, Any]) -> None:
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag or not tag.string:
        return
    try:
        d = json.loads(tag.string)
    except Exception:
        return
    try:
        data = d["props"]["initialState"]["productv2"]["productData"]["response"]["data"]
    except (KeyError, TypeError):
        return
    if not isinstance(data, dict):
        return
    if "product_name" not in out:
        name = data.get("name", "")
        if name:
            out["product_name"] = str(name)
    if "price" not in out:
        price = data.get("price")
        if price is not None:
            out["price"] = str(price)
    if "product_id" not in out:
        pid = data.get("id") or data.get("sku")
        if pid:
            out["product_id"] = str(pid)


def selector_row(html: str, spider: Optional[str]) -> Dict[str, Any]:
    """The spider's CSS selectors over one page, plus its per-spider fallbacks.

    A spider with no selectors and no fallback gets ``{}`` without parsing the
    page: the fleet parses under the GIL, one process per core, and a soup per
    page for nothing is its whole CPU budget.
    """
    selectors = SPIDER_SELECTORS.get(spider or "") or {}
    if not (selectors or spider in _LDJSON_SPIDERS or spider in _NEXTDATA_SPIDERS):
        return {}
    soup = BeautifulSoup(html, "html.parser")
    out: Dict[str, Any] = {}
    for field, selector_list in selectors.items():
        v = extract_with_fallback(soup, selector_list)
        if v:
            out[field] = v
    if spider in _LDJSON_SPIDERS:
        _ldjson_fallback(html, out)
    if spider in _NEXTDATA_SPIDERS:
        _nextdata_fallback(soup, out)
    return out


def portable_rows(html: str, url: str, source: Optional[str] = None) -> Tuple[List[Dict[str, Any]], str]:
    """The spider-independent tiers, in measured yield order, then per-source.

    Microdata and then `__NEXT_DATA__` are last among the portable tiers: each
    was measured only on pages the tiers above already fail, so appending them
    cannot change a page that parses today. The per-source tier returns nothing
    for a source without an extractor, so it too can only add rows.
    """
    rows = rows_from_jsonld(html, url)
    if rows:
        return rows, "jsonld"
    row = row_from_meta(html, url)
    if row:
        return [row], "meta"
    rows = rows_from_next_flight(html, url)
    if rows:
        return rows, "flight"
    rows = rows_from_microdata(html, url)
    if rows:
        return rows, "microdata"
    rows = rows_from_nextdata(html, url)
    if rows:
        return rows, "nextdata"
    rows = rows_from_source(html, url, source)
    if rows:
        return rows, "bysource"
    return [], "none"


def parse_rows(
    html: str,
    url: str,
    source: Optional[str] = None,
    hook: Optional[Callable[[str, str], Iterable[Dict[str, Any]]]] = None,
) -> Tuple[List[Dict[str, Any]], str]:
    """Rows for one archived page and the tier that produced them.

    A spider with a hook never runs selectors -- platform-base spiders have
    none, and the hook is their archived parser. Every tier falls through: the
    hook and the selectors are written against *current* markup, so on an old
    capture they routinely match nothing, or a name but not a price.

    A selector row without a price is a miss, not a result. It is banked only
    when every tier below also failed (tier ``selectors_noprice``), so a name
    is kept rather than dropped, and it can never displace a priced row.

    A priced selector row gives way only to a portable tier that finds several
    rows: selectors return one row per page, so on a category page they bank the
    page title while JSON-LD lists every product, and on a product page they miss
    the variants.
    """
    if hook is not None:
        try:
            rows = [r for r in hook(html, url) if r]
        except Exception:
            logger.debug("parse_html failed for %s", url, exc_info=True)
            rows = []
        if rows:
            return rows, "hook"
        return portable_rows(html, url, source)
    extracted = selector_row(html, source)
    rows, tier = portable_rows(html, url, source)
    if extracted.get("price") and len(rows) <= 1:
        return [extracted], "selectors"
    if rows:
        return rows, tier
    if extracted:
        return [extracted], "selectors_noprice"
    return [], "none"
