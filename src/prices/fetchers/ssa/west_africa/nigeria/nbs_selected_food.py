"""Nigeria NBS "Selected Food Prices Watch" — monthly item-level average retail prices.

The National Bureau of Statistics publishes a monthly XLSX with national item-level
average retail prices (Naira) for ~40 food staples, each with the current month's
average alongside prior-month and year-ago comparators, plus the highest/lowest
state. There is no stable per-month URL — each edition is announced on the
`/elibrary` catalog with its own numeric document id and its own XLSX filename
(observed: ``selected_food_oct_2024.xlsx`` — no fixed naming rule), so this fetcher
discovers the latest edition by searching the elibrary catalog for "Selected food
prices" and following the highest-dated hit to its resource link.

Verified live 2026-08-06: the elibrary catalog's own listing (both the unfiltered
`/elibrary` page and this search) has not surfaced anything newer than "Selected
Food Prices Watch (October 2024)", posted 2024-11-24 — NBS's public document
repository for this series has been stale for ~21 months as of this check, even
though NBS's own internal release calendar (a separate JS widget on the same page)
lists scheduled future editions through late 2026. This looks like NBS itself
stopped publishing to the public catalog, not a caching artifact (response carries
`Cache-Control: no-store, no-cache, must-revalidate`). The fetcher is written to
auto-discover whichever edition is current at run time, so it will pick up newer
editions automatically if/when NBS resumes uploading — no code change needed.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date, datetime

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Nigeria"
_CURRENCY = "NGN"
_SOURCE_KEY = "nbs_ng_food"
_IDENT = ["source_key", "observation_date", "item_name"]
_SEARCH_URL = (
    "https://nigerianstat.gov.ng/elibrary?queries%5Bsearch%5D=Selected+food+prices"
)
_ROW_RE = re.compile(
    r"<td>((?:Selected\s+[Ff]ood\s*[Pp]rices?)[^<]*)</td>.*?"
    r"<td>([A-Za-z]{3} [A-Za-z]{3} \d{1,2} \d{4})</td>.*?"
    r"elibrary/read/(\d+)",
    re.S,
)
_XLSX_RE = re.compile(r'href="([^"]+\.xlsx)"')
_AVG_COL_RE = re.compile(r"Average of ([A-Za-z]{3})-(\d{2})")


def _find_latest_edition(session) -> tuple[str, int] | None:
    try:
        r = session.get(_SEARCH_URL, timeout=30)
        r.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] elibrary search failed: %s", _SOURCE_KEY, exc)
        return None
    best: tuple[datetime, str, int] | None = None
    for title, date_str, doc_id in _ROW_RE.findall(r.text):
        try:
            posted = datetime.strptime(date_str, "%a %b %d %Y")
        except ValueError:
            continue
        if best is None or posted > best[0]:
            best = (posted, title.strip(), int(doc_id))
    if best is None:
        return None
    return best[1], best[2]


def _resolve_xlsx_url(session, doc_id: int) -> str | None:
    read_url = f"https://nigerianstat.gov.ng/elibrary/read/{doc_id}"
    try:
        r = session.get(read_url, timeout=30)
        r.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] read page fetch failed %s: %s", _SOURCE_KEY, read_url, exc)
        return None
    m = _XLSX_RE.search(r.text)
    return m.group(1) if m else None


def _current_avg_column(columns: list[str]) -> tuple[str, date] | None:
    best: tuple[date, str] | None = None
    for col in columns:
        m = _AVG_COL_RE.match(str(col).strip())
        if not m:
            continue
        try:
            d = datetime.strptime(f"01-{m.group(1)}-{m.group(2)}", "%d-%b-%y").date()
        except ValueError:
            continue
        if best is None or d > best[0]:
            best = (d, col)
    return (best[1], best[0]) if best else None


def _rows(xlsx_bytes: bytes, source_url: str, cutoff: date) -> list[dict]:
    xl = pd.ExcelFile(io.BytesIO(xlsx_bytes))
    sheet = next((s for s in xl.sheet_names if "food" in s.lower()), xl.sheet_names[0])
    df = xl.parse(sheet)
    if "Items Label" not in df.columns:
        logger.warning("[%s] no 'Items Label' column in sheet %s", _SOURCE_KEY, sheet)
        return []
    found = _current_avg_column(list(df.columns))
    if not found:
        logger.warning(
            "[%s] no 'Average of Mon-YY' column found in sheet %s", _SOURCE_KEY, sheet
        )
        return []
    avg_col, obs_date = found
    if obs_date <= cutoff:
        return []
    ts = get_scrape_ts()
    out: list[dict] = []
    for _, r in df.iterrows():
        item = r.get("Items Label")
        if not isinstance(item, str) or not item.strip():
            continue
        try:
            price = float(r.get(avg_col))
        except (TypeError, ValueError):
            continue
        if not 0 < price < 1_000_000:
            continue
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "monthly",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": item.strip(),
            "price_local": round(price, 4),
            "currency": _CURRENCY,
            "unit": None,
            "source_url": source_url,
            "notes": f"National average, column '{avg_col}'",
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        out.append(row)
    return out


def fetch_nbs_ng_food(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    found = _find_latest_edition(session)
    if not found:
        logger.warning("[%s] no edition found on elibrary catalog", _SOURCE_KEY)
        return None
    title, doc_id = found
    xlsx_href = _resolve_xlsx_url(session, doc_id)
    if not xlsx_href:
        logger.warning(
            "[%s] no xlsx resource link on read page for doc %d", _SOURCE_KEY, doc_id
        )
        return None
    xlsx_url = (
        xlsx_href
        if xlsx_href.startswith("http")
        else f"https://nigerianstat.gov.ng{xlsx_href}"
    )
    try:
        resp = session.get(xlsx_url, timeout=60)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] xlsx fetch failed %s: %s", _SOURCE_KEY, xlsx_url, exc)
        return None
    rows = _rows(resp.content, xlsx_url, cutoff)
    logger.info(
        "[%s] %d rows from '%s' (doc_id=%d, cutoff=%s)",
        _SOURCE_KEY,
        len(rows),
        title,
        doc_id,
        cutoff,
    )
    return pd.DataFrame(rows) if rows else None
