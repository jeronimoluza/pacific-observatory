"""Iwacu Open Data Burundi historical pump fuel prices.

Iwacu republishes ISTEEBU's 1980-January 2018 Burundi pump-price dataset
as a CSV/XLSX table for essence, gasoil and pétrole. The fetcher downloads
the CSV, detects the date/year columns and product columns, then emits one
row per observation date and product in BIF/litre.
"""

from __future__ import annotations

import io
import logging
import re
import unicodedata
from datetime import date

import pandas as pd

from core.http import make_session

logger = logging.getLogger(__name__)

_CSV_URL = (
    "https://iwacu-burundi.org/opendata/wp-content/uploads/2018/01/"
    "IOD_BU_145_FR_-evolution_prix_carburant.csv"
)
_XLSX_URL = _CSV_URL.rsplit(".", 1)[0] + ".xlsx"
_COUNTRY = "Burundi"
_CURRENCY = "BIF"
_SOURCE_KEY = "iwacu_bi_historical"

_MONTHS = {
    "janvier": 1,
    "jan": 1,
    "fevrier": 2,
    "février": 2,
    "fev": 2,
    "mars": 3,
    "avril": 4,
    "avr": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "juil": 7,
    "aout": 8,
    "août": 8,
    "septembre": 9,
    "sept": 9,
    "octobre": 10,
    "oct": 10,
    "novembre": 11,
    "nov": 11,
    "decembre": 12,
    "décembre": 12,
    "dec": 12,
}
_PRODUCTS = {
    "essence": "essence",
    "gasoil": "gasoil",
    "gas oil": "gasoil",
    "petrole": "pétrole",
    "pétrole": "pétrole",
}


def _norm(value: object) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text)


def _parse_number(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "nd", "n/a", "-"}:
        return None
    text = text.replace("\u00a0", "").replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(",", ".")
    try:
        price = float(text)
    except ValueError:
        return None
    return price if price > 0 else None


def _read_table(content: bytes) -> pd.DataFrame | None:
    for encoding in ("utf-8-sig", "latin1"):
        try:
            df = pd.read_csv(
                io.BytesIO(content), sep=None, engine="python", encoding=encoding
            )
        except Exception:
            continue
        if len(df.columns) > 1:
            return df
    return None


def _read_xlsx(session) -> pd.DataFrame | None:
    try:
        resp = session.get(_XLSX_URL, timeout=60)
    except Exception:
        logger.exception("[iwacu_bi] XLSX fetch failed")
        return None
    if resp.status_code != 200:
        return None
    try:
        return pd.read_excel(io.BytesIO(resp.content))
    except Exception:
        logger.exception("[iwacu_bi] XLSX parse failed")
        return None


def _find_col(columns: list[str], names: tuple[str, ...]) -> str | None:
    for col in columns:
        low = _norm(col)
        if any(name in low for name in names):
            return col
    return None


def _month_from_value(value: object) -> int | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (int, float)) and not pd.isna(value):
        month = int(value)
        return month if 1 <= month <= 12 else None
    low = _norm(value)
    if low.isdigit():
        month = int(low)
        return month if 1 <= month <= 12 else None
    for name, month in _MONTHS.items():
        if _norm(name) in low:
            return month
    return None


def _date_from_row(row: pd.Series, columns: list[str]) -> date | None:
    year_col = _find_col(columns, ("annee", "year"))
    month_col = _find_col(columns, ("mois", "month"))
    if year_col is not None:
        try:
            year = int(float(str(row.get(year_col)).strip()))
        except (TypeError, ValueError):
            year = None
        if year:
            month = _month_from_value(row.get(month_col)) if month_col else None
            try:
                return date(year, month or 1, 1)
            except ValueError:
                return None

    date_col = _find_col(columns, ("date", "periode", "période"))
    if date_col is None and columns:
        date_col = columns[0]
    value = row.get(date_col) if date_col else None
    if value is None or pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return date(value.year, value.month, value.day)
    parsed = pd.to_datetime(value, dayfirst=True, errors="coerce")
    if not pd.isna(parsed):
        return date(int(parsed.year), int(parsed.month), int(parsed.day))
    text = _norm(value)
    year_match = re.search(r"(19\d{2}|20\d{2})", text)
    if not year_match:
        return None
    year = int(year_match.group(1))
    month = _month_from_value(text) or 1
    try:
        return date(year, month, 1)
    except ValueError:
        return None


def _product_columns(columns: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for col in columns:
        low = _norm(col)
        for token, label in _PRODUCTS.items():
            if _norm(token) in low:
                out.setdefault(col, label)
    return out


def fetch_iwacu_bi(cutoff: date) -> pd.DataFrame | None:
    session = make_session()
    try:
        resp = session.get(_CSV_URL, timeout=60)
    except Exception:
        logger.exception("[iwacu_bi] CSV fetch failed")
        return None
    df = _read_table(resp.content) if resp.status_code == 200 else None
    if df is None:
        df = _read_xlsx(session)
    if df is None or df.empty:
        logger.info("[iwacu_bi] no table loaded")
        return None

    df = df.dropna(how="all")
    columns = [str(col).strip() for col in df.columns]
    df.columns = columns
    product_cols = _product_columns(columns)
    if not product_cols:
        logger.warning("[iwacu_bi] no product columns detected: %s", columns)
        return None

    rows: list[dict] = []
    for _, row in df.iterrows():
        obs_date = _date_from_row(row, columns)
        if obs_date is None or obs_date <= cutoff:
            continue
        for col, product in product_cols.items():
            price = _parse_number(row.get(col))
            if price is None:
                continue
            rows.append(
                {
                    "observation_date": obs_date.isoformat(),
                    "country": _COUNTRY,
                    "fuel_product": product,
                    "price_local": price,
                    "currency": _CURRENCY,
                    "source_key": _SOURCE_KEY,
                    "unit": "L",
                }
            )

    if not rows:
        logger.info("[iwacu_bi] no rows after cutoff %s", cutoff)
        return None
    out = (
        pd.DataFrame(rows)
        .drop_duplicates(subset=["observation_date", "fuel_product"])
        .sort_values(["observation_date", "fuel_product"])
        .reset_index(drop=True)
    )
    logger.info(
        "[iwacu_bi] %d rows (%s → %s)",
        len(out),
        out["observation_date"].iloc[0],
        out["observation_date"].iloc[-1],
    )
    return out


__all__ = ["fetch_iwacu_bi"]
