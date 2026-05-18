"""Kyrgyz Republic — National Statistical Committee monthly fuel-price XLS.

The XLS at /media/files/<guid>.xls is linked from /en/daily-prices/ as
"Fuels and lubricants". It contains 125+ sheets (one per month since 2016-01),
each holding average consumer prices (sm/L) for several fuel products across
Kyrgyzstan, with working-day daily columns plus a monthly average.

Layout (per sheet):
  - Row 0: title in three languages (Kyrgyz / English / Russian).
  - Row 3 col 1+: English day headers, e.g. ``May 1``, ``May 4`` ...,
    plus an ``Average price for <month> <year>`` column.
  - For each product:
      - one header row with the product name in col 1
        (``Gasoline A-95`` / ``Gasoline A-92`` / ``Gasoline A-80`` /
        ``Diesel fuel``),
      - then a ``Kyrgyz Republic`` row (col 1) with the national prices,
      - then city rows we ignore (we keep only the national series).

Not every sheet has every product — older sheets list A-80; more recent
sheets (e.g. May 2026) skip A-80. The parser is product-agnostic.
"""

import io
import logging
import re
from datetime import date, datetime

import pandas as pd

from core.http import make_session

logger = logging.getLogger(__name__)

# TODO(future): re-parse https://www.stat.gov.kg/en/daily-prices/ for the
# current "Fuels and lubricants" XLS link if this static URL ever 404s.
_URL = "https://www.stat.gov.kg/media/files/cfdf6deb-d10c-4e34-b92d-a43198e097a8.xls"
_COUNTRY = "Kyrgyz Republic"
_CURRENCY = "KGS"
_SOURCE_KEY = "stat_kg_monthly"

_RU_MONTHS = {
    "январь": 1,
    "февраль": 2,
    "март": 3,
    "апрель": 4,
    "май": 5,
    "июнь": 6,
    "июль": 7,
    "август": 8,
    "сентябрь": 9,
    "октябрь": 10,
    "ноябрь": 11,
    "декабрь": 12,
}

_EN_MONTHS = {
    "January": 1,
    "February": 2,
    "March": 3,
    "April": 4,
    "May": 5,
    "June": 6,
    "July": 7,
    "August": 8,
    "September": 9,
    "October": 10,
    "November": 11,
    "December": 12,
}

_PRODUCT_LABELS = {
    "Gasoline A-95": "Gasoline A-95",
    "Gasoline A-92": "Gasoline A-92",
    "Gasoline A-80": "Gasoline A-80",
    "Diesel fuel": "Diesel",
}

_NATIONAL_LABEL_RE = re.compile(r"\bKyrgyz\s+Republic\b", re.IGNORECASE)
_DAY_HEADER_RE = re.compile(r"^\s*([A-Za-z]+)\s+(\d{1,2})\s*$")


def _parse_sheet_name(name: str) -> tuple[int, int] | None:
    """Parse 'май_2026' / 'январь_2016 ' → (year, month)."""
    cleaned = name.strip().lower().replace("\xa0", " ")
    m = re.match(r"([а-яё]+)[_\s]+(\d{4})", cleaned)
    if not m:
        return None
    month = _RU_MONTHS.get(m.group(1))
    if month is None:
        return None
    return int(m.group(2)), month


def _build_date_columns(
    header_row: pd.Series, sheet_year: int, sheet_month: int
) -> dict[int, str]:
    """Map column-index → YYYY-MM-DD using the English day-header row."""
    out: dict[int, str] = {}
    for col_idx, raw in header_row.items():
        if pd.isna(raw):
            continue
        text = str(raw)
        # Skip 'Average price for ...' columns.
        if "Average price" in text:
            continue
        m = _DAY_HEADER_RE.match(text)
        if not m:
            continue
        month_name, day_str = m.group(1), int(m.group(2))
        month = _EN_MONTHS.get(month_name)
        if month is None:
            continue
        # Sanity: day-headers should match the sheet's own month; if not, skip.
        if month != sheet_month:
            continue
        try:
            d = date(sheet_year, sheet_month, day_str)
        except ValueError:
            continue
        out[col_idx] = d.isoformat()
    return out


def _parse_sheet(df: pd.DataFrame, sheet_year: int, sheet_month: int) -> list[dict]:
    """Extract national rows for every product present on the sheet."""
    if df.shape[0] < 5 or df.shape[1] < 5:
        return []

    # Row 3 holds the English day-header row used by every sheet we've seen.
    date_cols = _build_date_columns(df.iloc[3], sheet_year, sheet_month)
    if not date_cols:
        return []

    en_col = df.iloc[:, 1].astype(str).fillna("")
    rows: list[dict] = []
    for i, label in en_col.items():
        product = None
        for key, canonical in _PRODUCT_LABELS.items():
            if key in label:
                product = canonical
                break
        if product is None:
            continue

        # National row is normally i+1 but may include blank rows; search a small window.
        national_idx = None
        for j in range(i + 1, min(i + 4, len(en_col))):
            if _NATIONAL_LABEL_RE.search(en_col.iloc[j]):
                national_idx = j
                break
        if national_idx is None:
            continue

        national_row = df.iloc[national_idx]
        for col_idx, obs_date in date_cols.items():
            cell = national_row.iloc[col_idx]
            try:
                price = float(cell)
            except (TypeError, ValueError):
                continue
            if not (price > 0):
                continue
            rows.append(
                {
                    "observation_date": obs_date,
                    "country": _COUNTRY,
                    "fuel_product": product,
                    "price_local": round(price, 4),
                    "currency": _CURRENCY,
                    "source_key": _SOURCE_KEY,
                    "unit": "L",
                }
            )
    return rows


def fetch_kg_stat(cutoff: date) -> pd.DataFrame | None:
    """Fetch Kyrgyz Republic national fuel prices from stat.gov.kg."""
    session = make_session()
    resp = session.get(_URL, timeout=120)
    resp.raise_for_status()
    if (
        "excel" not in resp.headers.get("Content-Type", "").lower()
        and len(resp.content) < 50_000
    ):
        raise RuntimeError(
            f"stat.gov.kg returned non-XLS or short response from {_URL}; "
            f"the static GUID may have rotated — re-discover from /en/daily-prices/."
        )

    xl = pd.ExcelFile(io.BytesIO(resp.content))
    all_rows: list[dict] = []
    for sheet in xl.sheet_names:
        ym = _parse_sheet_name(sheet)
        if ym is None:
            logger.debug("[stat_kg] skipping unparseable sheet: %r", sheet)
            continue
        sheet_year, sheet_month = ym
        # Cheap pre-filter: skip sheets entirely before cutoff month.
        last_of_month = date(sheet_year, sheet_month, 28)
        if last_of_month < cutoff:
            continue
        df = pd.read_excel(xl, sheet_name=sheet, header=None)
        sheet_rows = _parse_sheet(df, sheet_year, sheet_month)
        for r in sheet_rows:
            obs = datetime.strptime(r["observation_date"], "%Y-%m-%d").date()
            if obs <= cutoff:
                continue
            all_rows.append(r)

    if not all_rows:
        return None
    return pd.DataFrame(all_rows)
