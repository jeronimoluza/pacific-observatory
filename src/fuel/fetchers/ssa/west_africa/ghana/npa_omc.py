"""Ghana NPA ex-pump (retail) prices of OMCs and LPGMCs, one row per company.

NPA publishes a near-daily workbook "Ex-Pump Prices of OMCs and LPGMCs as of
<date>" in its directory-indexed uploads (from April 2024). In Ghana
"ex-pump" is the price at the pump. Older workbooks hold one sheet; recent
ones keep a rolling year of daily sheets, so the newest file is parsed first
and files whose date an earlier sheet already covered are skipped.
"""

from __future__ import annotations

import io
import logging
import re
import time
from datetime import date
from urllib.parse import urljoin

import pandas as pd

from core.http import make_session

logger = logging.getLogger(__name__)

_UPLOADS = "https://npa.gov.gh/wp-content/uploads"
_FIRST = date(2024, 4, 1)
_COUNTRY = "Ghana"
_CURRENCY = "GHS"
_SOURCE_KEY = "npa_gh_omc_pump"
_THROTTLE_S = 0.7

_HREF_RE = re.compile(r'href="([^"]*Pump-Prices-of-OMCs-and-LPGMCs[^"]*\.xlsx)"', re.I)
_DATE_RE = re.compile(
    r"(\d{1,2})(?:st|nd|rd|th)?[\s-]+([A-Za-z]{3,9})\.?,?[\s-]+(\d{4}|\d{2})",
    re.I,
)
_MONTHS = {
    m: i
    for i, m in enumerate(
        [
            "jan",
            "feb",
            "mar",
            "apr",
            "may",
            "jun",
            "jul",
            "aug",
            "sep",
            "oct",
            "nov",
            "dec",
        ],
        start=1,
    )
}
# Header prefix → product; checked in order ("PREMIUM PETROL" before "PETROL").
_HEADERS = [
    ("premium petrol", "Premium Petrol"),
    ("regular petrol", "Petrol"),
    ("petrol", "Petrol"),
    ("diesel", "Diesel"),
    ("lpg", "LPG"),
    ("kerosene", "Kerosene"),
]


def _parse_date(text: str) -> date | None:
    m = _DATE_RE.search(text.replace("_", " "))
    if not m:
        return None
    month = _MONTHS.get(m.group(2)[:3].lower())
    year = int(m.group(3))
    if not month:
        return None
    try:
        return date(year + 2000 if year < 100 else year, month, int(m.group(1)))
    except ValueError:
        return None


def _discover(session, cutoff: date) -> list[tuple[date, str]]:
    found: dict[str, date] = {}
    today = date.today()
    start = max(_FIRST, cutoff.replace(day=1))
    year, month = start.year, start.month
    while (year, month) <= (today.year, today.month):
        url = f"{_UPLOADS}/{year}/{month:02d}/"
        try:
            resp = session.get(url, timeout=60)
            if resp.status_code == 200:
                for href in _HREF_RE.findall(resp.text):
                    obs = _parse_date(href.rsplit("/", 1)[-1])
                    if obs and obs > cutoff:
                        found[urljoin(url, href)] = obs
        except Exception:
            logger.exception("[npa_gh_omc] directory fetch failed: %s", url)
        time.sleep(_THROTTLE_S)
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return sorted(((d, u) for u, d in found.items()), reverse=True)


def _price(raw) -> float | None:
    if isinstance(raw, str):
        try:
            raw = float(raw.replace(",", "").strip())
        except ValueError:
            return None
    if isinstance(raw, (int, float)) and raw > 0:
        return float(raw)
    return None


def _parse_sheet(rows: list[tuple]) -> tuple[date | None, list[tuple[str, str, float]]]:
    """Return (sheet date from its title, [(company, product, price)])."""
    obs = None
    header_idx = None
    for i, row in enumerate(rows[:20]):
        cells = [str(c) for c in row if c is not None]
        text = " ".join(cells)
        if obs is None and re.search(r"\bAS (?:OF|AT)\b", text, re.I):
            obs = _parse_date(text)
        if any(c.strip().upper() == "COMPANY" for c in cells):
            header_idx = i
            break
    if header_idx is None:
        return obs, []
    header = [str(c or "").strip().lower() for c in rows[header_idx]]
    company_col = header.index("company")
    cols = {}
    for j, h in enumerate(header):
        product = next((p for k, p in _HEADERS if h.startswith(k)), None)
        if product and product not in cols.values():
            cols[j] = product
    out = []
    for row in rows[header_idx + 1 :]:
        name = row[company_col] if company_col < len(row) else None
        if not isinstance(name, str) or not name.strip():
            continue
        name = " ".join(name.split())
        if re.match(r"(max|min|average)\b", name, re.I):
            break
        for j, product in cols.items():
            price = _price(row[j]) if j < len(row) else None
            if price is not None:
                out.append((name, product, price))
    return obs, out


def _read_workbook(content: bytes) -> list[tuple[str, list[tuple]]]:
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    try:
        return [
            (ws.title, list(ws.iter_rows(values_only=True))) for ws in wb.worksheets
        ]
    finally:
        wb.close()


def fetch_npa_gh_omc(cutoff: date) -> pd.DataFrame | None:
    session = make_session()
    seen: set[date] = set()
    records: list[tuple[date, str, str, float]] = []
    for file_date, url in _discover(session, cutoff):
        if file_date in seen:
            continue
        try:
            resp = session.get(url, timeout=120)
            resp.raise_for_status()
            sheets = _read_workbook(resp.content)
        except Exception:
            logger.exception("[npa_gh_omc] workbook failed: %s", url)
            continue
        new_dates = set()
        for title, rows in sheets:
            obs, prices = _parse_sheet(rows)
            obs = obs or _parse_date(title) or (file_date if len(sheets) == 1 else None)
            if obs is None or obs <= cutoff or obs in seen or not prices:
                continue
            new_dates.add(obs)
            records.extend((obs, *p) for p in prices)
        seen |= new_dates
        logger.info(
            "[npa_gh_omc] %s: %d new dates", url.rsplit("/", 1)[-1], len(new_dates)
        )
        time.sleep(_THROTTLE_S)
    if not records:
        logger.info("[npa_gh_omc] no rows after cutoff %s", cutoff)
        return None

    df = pd.DataFrame(
        records, columns=["obs", "station", "fuel_product", "price_local"]
    )
    # Same company spelled differently across sheets → newest spelling.
    latest = df.sort_values("obs").groupby(df["station"].str.lower())["station"].last()
    df["station"] = df["station"].str.lower().map(latest)
    df = df.drop_duplicates(subset=["obs", "station", "fuel_product"])
    df = pd.DataFrame(
        {
            "observation_date": df["obs"].map(date.isoformat),
            "country": _COUNTRY,
            "fuel_product": df["fuel_product"],
            "price_local": df["price_local"],
            "currency": _CURRENCY,
            "source_key": _SOURCE_KEY,
            "unit": df["fuel_product"].map(
                lambda p: "kilogram" if p == "LPG" else "litre"
            ),
            "address": df["station"],
            "station": df["station"],
        }
    ).sort_values(["observation_date", "fuel_product", "station"])
    logger.info(
        "[npa_gh_omc] %d rows, %d dates (%s → %s)",
        len(df),
        df["observation_date"].nunique(),
        df["observation_date"].min(),
        df["observation_date"].max(),
    )
    return df.reset_index(drop=True)


__all__ = ["fetch_npa_gh_omc"]
