"""TCB (Trading Corporation of Bangladesh) daily essential-commodity prices.

The Daily Retail Market Price Survey (RMPS) page lists dated XLSX files
(Oracle Cloud object storage, no auth), most recent first. Re-verified live
2026-08-06: GET https://tcb.gov.bd/pages/daily-rmps -> 200, 90.8KB HTML; the
first `https://objectstorage...xlsx` link on the page is the current day's
report. Downloaded and parsed: sheet 'Daily retail price', header rows carry
the Bangla report date (e.g. day/month-name/year in Bangla digits), data rows
from row 9 onward: item name (Bangla), unit (Bangla), min price, max price in
BDT. Sample: fragrant/polao rice, 'per kg', 160-200 BDT.

Narrow essential-commodities basket (rice, edible oil, sugar, lentils/pulses,
onion) but trivial to fetch: one XLSX per day, stable link pattern, no auth.
"""

from __future__ import annotations

import io
import logging
import re
import tempfile
from datetime import date
from functools import lru_cache
from pathlib import Path

import certifi
import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

# tcb.gov.bd presents a valid Sectigo cert (a shared *.gov.bd multi-SAN cert that
# does list tcb.gov.bd) but serves an INCOMPLETE chain: the issuing intermediate
# is missing, so the default trust store cannot build a path to the root and
# verification fails. The fix is to supply that intermediate, not to skip
# verification -- these are the prices we ingest, so an unauthenticated transport
# is a data-integrity hole, not just a security one.
_CHAIN_PEM = Path(__file__).with_name("_tcb_gov_bd_chain.pem")


@lru_cache(maxsize=1)
def _ca_bundle() -> str:
    bundle = Path(tempfile.gettempdir()) / "tcb_gov_bd_ca_bundle.pem"
    bundle.write_bytes(
        Path(certifi.where()).read_bytes() + b"\n" + _CHAIN_PEM.read_bytes()
    )
    return str(bundle)


_PAGE_URL = "https://tcb.gov.bd/pages/daily-rmps"
_COUNTRY = "Bangladesh"
_CURRENCY = "BDT"
_SOURCE_KEY = "bd_tcb_daily_rmps"
_IDENT = ["source_key", "observation_date", "item_name", "unit"]
_XLSX_RE = re.compile(r'href="(https://objectstorage[^"]+\.xlsx)"')

# Bangla digits 0-9 -> ASCII, used to parse the report date out of the sheet header.
_BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
_BN_MONTHS = {
    "জানুয়ারি": 1,
    "ফেব্রুয়ারি": 2,
    "মার্চ": 3,
    "এপ্রিল": 4,
    "মে": 5,
    "জুন": 6,
    "জুলাই": 7,
    "আগষ্ট": 8,
    "আগস্ট": 8,
    "সেপ্টেম্বর": 9,
    "অক্টোবর": 10,
    "নভেম্বর": 11,
    "ডিসেম্বর": 12,
}


def _parse_report_date(header_text: str) -> date | None:
    m = re.search(r"([০-৯]{1,2})\s+([^\s,০-৯]+)\s+([০-৯]{4})", header_text)
    if not m:
        return None
    day = int(m.group(1).translate(_BN_DIGITS))
    month = _BN_MONTHS.get(m.group(2).strip())
    year = int(m.group(3).translate(_BN_DIGITS))
    if not month:
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _rows(xlsx_bytes: bytes, xlsx_url: str, cutoff: date) -> list[dict]:
    wb = pd.read_excel(io.BytesIO(xlsx_bytes), sheet_name=0, header=None)
    header_blob = " ".join(
        str(v) for v in wb.iloc[:6, 0].tolist() if isinstance(v, str)
    )
    obs_date = _parse_report_date(header_blob)
    if obs_date is None or obs_date <= cutoff:
        return []
    out: list[dict] = []
    ts = get_scrape_ts()
    for _, r in wb.iloc[8:].iterrows():
        name = r.get(0)
        unit = r.get(1)
        if not isinstance(name, str) or not name.strip():
            continue
        try:
            lo = float(r.get(2))
            hi = float(r.get(3))
        except (TypeError, ValueError):
            continue
        if lo <= 0 and hi <= 0:
            continue
        avg = (lo + hi) / 2 if hi > 0 else lo
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "daily",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": name.strip(),
            "price_local": round(avg, 2),
            "currency": _CURRENCY,
            "unit": str(unit).strip() if isinstance(unit, str) else None,
            "source_url": xlsx_url,
            "notes": f"min={lo}; max={hi}",
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        out.append(row)
    return out


def fetch_bd_tcb_daily_rmps(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    try:
        page = session.get(_PAGE_URL, timeout=30, verify=_ca_bundle())
        page.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] page fetch failed: %s", _SOURCE_KEY, exc)
        return None
    m = _XLSX_RE.search(page.text)
    if not m:
        logger.warning("[%s] no xlsx link found on daily-rmps page", _SOURCE_KEY)
        return None
    xlsx_url = m.group(1)
    try:
        resp = session.get(xlsx_url, timeout=60)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] xlsx fetch failed: %s", _SOURCE_KEY, exc)
        return None
    rows = _rows(resp.content, xlsx_url, cutoff)
    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
