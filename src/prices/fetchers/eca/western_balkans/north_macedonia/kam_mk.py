"""
KAM Market (North Macedonia) — https://www.kam.com.mk/.

KAM has no scrapable webshop (its "webshop" AJAX pages only ever render the
sitewide rotating weekly-promo carousel; non-promoted products render zero
price — confirmed a promo-flyer trap, not built). Its real catalog is a
different, better surface: the statutorily-mandated per-store price-
transparency PDF that North Macedonian retailers must publish. The store
locator page (`/kam-prodavnici.nspx`) lists every physical store, and
`POST /ShopsWeb/LoadShopList` (no auth) returns each store's `ShopFiles`
entry — a same-day PDF at `/{RelativePath}` (e.g. `/2026/08/31/95.pdf`),
freshly regenerated every morning (`DateUploaded` confirmed same-day live).

The PDF is a genuine full-range price list — ~165 pages, ~11 data rows per
page (~1,800 SKUs), spanning the whole store assortment (bakery, dairy,
snacks, drinks, household, personal care) with columns: product name, sale
price ("Продажна цена" — the price the customer pays right now), unit
price, brand/description, in-stock flag, regular price, and (when active)
a promo sub-table. This is the opposite of the promo-flyer pattern: every
row carries a normal, always-present sale price; the promo columns are
almost always empty (no discount active) and are not needed for this
fetcher — "Продажна цена" is the row's price whether or not a discount is
running.

One representative store is walked per run (Скопје / Аеродром — a
full-format store carrying bakery + cooked-food + fresh-fish counters per
its own `Tags`), not all ~90 stores — KAM does not publish per-store price
variation in a way this pipeline models, and one store's daily assortment
is already a substantial, wide retailer_sku catalog. `coicop_classification:
classifier` — the catalog spans most COICOP divisions, so no `_COICOP_MAP`
is declared.

`pdfplumber.extract_tables()` reads the file as a clean bordered table
(verified: header row + continuation row match exactly, data rows have the
same 9-column shape) — no OCR needed, `extract_text()` is not used.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd
import pdfplumber

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_BASE = "https://www.kam.com.mk"
_SHOPLIST_URL = f"{_BASE}/ShopsWeb/LoadShopList"
_COUNTRY = "North Macedonia"
_CURRENCY = "MKD"
_SOURCE_KEY = "mk_kam"
_PREFERRED_MUNICIPALITY = "Аеродром"  # Skopje, full-format store (bakery/cooked/fish)
_HEADER_MARKER = "Назив на"
_PRICE_RE = re.compile(r"([\d.,]+)\s*ден")
_IDENT = ["source_key", "observation_date", "item_name", "notes"]


def _parse_price(raw: str | None) -> float | None:
    """Parse the sale/regular-price cell.

    This column is always whole denars: "." only ever appears as a
    thousands separator ("1.229ден." = 1229, verified: every "." in this
    column is followed by exactly 3 digits, never a decimal fraction — the
    "100 гр = 9.20 ден." unit-price column is the one with real decimals,
    and it is a different column, not parsed here). "," is treated as a
    decimal separator if it ever appears, for robustness.
    """
    if not raw:
        return None
    m = _PRICE_RE.search(raw.replace("\n", " "))
    if not m:
        return None
    num = m.group(1)
    if "," in num:
        num = num.replace(".", "").replace(",", ".")
    else:
        num = num.replace(".", "")
    try:
        return float(num)
    except ValueError:
        return None


def _pick_store(stores: list[dict]) -> dict | None:
    candidates = [s for s in stores if s.get("ShopFiles")]
    if not candidates:
        return None
    for s in candidates:
        if s.get("Municipality") == _PREFERRED_MUNICIPALITY:
            return s
    return candidates[0]


def _parse_pdf(content: bytes, source_url: str, cutoff_date: date) -> list[dict]:
    ts = get_scrape_ts()
    rows: list[dict] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for r in table:
                    if not r or not r[0] or _HEADER_MARKER in r[0]:
                        continue
                    name = re.sub(r"\s+", " ", r[0]).strip()
                    price = _parse_price(r[1] if len(r) > 1 else None)
                    if not name or price is None:
                        continue
                    desc = (
                        re.sub(r"\s+", " ", r[3]).strip() if len(r) > 3 and r[3] else ""
                    )
                    available = (r[4].strip() == "Да") if len(r) > 4 and r[4] else True
                    item_name = f"{name} {desc}".strip() if desc else name
                    row = {
                        "observation_date": cutoff_date.isoformat(),
                        "period_kind": "snapshot",
                        "country": _COUNTRY,
                        "source_key": _SOURCE_KEY,
                        "item_name": item_name[:500],
                        "price_local": price,
                        "currency": _CURRENCY,
                        "unit": "each",
                        "source_url": source_url,
                        "notes": f"available={available}",
                        "scrape_ts": ts,
                        "observation_hash": None,
                    }
                    row["observation_hash"] = make_hash(row, _IDENT)
                    rows.append(row)
    return rows


def fetch_kam_mk(cutoff: date) -> pd.DataFrame | None:
    session = get_session()

    try:
        resp = session.post(_SHOPLIST_URL, timeout=30)
        resp.raise_for_status()
        stores = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] store list fetch failed: %s", _SOURCE_KEY, exc)
        return None

    store = _pick_store(stores)
    if store is None:
        logger.warning("[%s] no store with a published price list", _SOURCE_KEY)
        return None

    shop_file = store["ShopFiles"][0]
    rel_path = shop_file["RelativePath"]
    # DateUploaded is a .NET JSON date: "/Date(1788127200000)/" (epoch ms).
    m = re.search(r"/Date\((\d+)\)/", shop_file.get("DateUploaded", "") or "")
    if not m:
        logger.warning("[%s] unparseable DateUploaded on %s", _SOURCE_KEY, rel_path)
        return None
    uploaded_date = date.fromtimestamp(int(m.group(1)) / 1000)
    if uploaded_date <= cutoff:
        logger.info(
            "[%s] price list not updated since cutoff (%s <= %s)",
            _SOURCE_KEY,
            uploaded_date,
            cutoff,
        )
        return None

    pdf_url = f"{_BASE}/{rel_path}"
    try:
        pdf_resp = session.get(pdf_url, timeout=60)
        pdf_resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] PDF fetch failed (%s): %s", _SOURCE_KEY, pdf_url, exc)
        return None

    rows = _parse_pdf(pdf_resp.content, pdf_url, uploaded_date)
    logger.info(
        "[%s] store=%s (%s) rows=%d date=%s",
        _SOURCE_KEY,
        store.get("Name"),
        store.get("Municipality"),
        len(rows),
        uploaded_date,
    )
    return pd.DataFrame(rows) if rows else None
