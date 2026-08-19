"""Tuvalu Central Statistics Division (stats.gov.tv) — Consumer Price Index, quarterly.

TCSD publishes a quarterly CPI release (Mar/Jun/Sep/Dec) as a WordPress post plus a
"CPI Release Tables" XLSX attachment listed on the Documents Library page
(stats.gov.tv/documents-library/, WP File Download plugin — wpfd_downloadlink hrefs
of the form /download/30/consumer-price-index/<id>/<slug>). Verified live 2026-08-11:
the RSS feed at /category/economics/consumer-price-index/feed/ enumerates every
release back to 2018 (cheapest full-history discovery, per the onboarding brief);
the Documents Library lists the same download links directly, newest first, and each
link serves the XLSX bytes with no ".xlsx" suffix needed on the URL. This fetcher
walks the Documents Library rather than the RSS + per-release-page hop because the
XLSX link is already there in one GET, no second page fetch required.

Each release's XLSX carries the FULL cumulative series (not just the new quarter),
so the fetcher only needs to resolve the single latest "release-tables" link — same
pattern as the Tunisia INS fetcher. Sheet "T2" ("PRICES INDICES BY QUARTERS") holds a
wide table: item-group label (rows) x quarter-end date (columns), raw index level.
Base period: 2019 Q4 = 1000 (confirmed — every group column reads exactly 1000 on
2019-12-04/2019-12-01 depending on year).

TCSD's own item-group scheme is NOT the standard COICOP-2018 grouping — it's a
flatter, Tuvalu-specific basket (6 top-level groups, food subgroups don't split
fruit/vegetables, "Miscellaneous" is a real catch-all group). Mapped to the closest
COICOP-2018 leaf/group per label below; genuinely ambiguous or catch-all rows are
dropped rather than forced into a colliding or misleading code (mirrors the INS
Tunisia fetcher's handling of its two ambiguous French labels). Section-header rows
("1. FOOD", "2. ALCOHOL & SMOKES", ...) carry no data in this sheet and are skipped
implicitly (all value cells NaN).

Emits IndexObservation rows (analytical_role: cpi_benchmark).
coicop_classification: publisher_labeled (static _COICOP_MAP below).

Dropped rows (no sanctioned code / too ambiguous to assign safely):
  - "Total All Group Expenditure" — all-items headline, no sanctioned sentinel (open
    design question in the onboarding skill).
  - "1.6 VEGETABLES AND FRUITS" — combines COICOP 01.1.6 (fruit) and 01.1.7
    (vegetables) into one series; no single COICOP leaf covers both.
  - "6 MISCELLANEOUS GROUP", "6.6 MISCELLANEOUS" — true catch-all buckets.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Tuvalu"
_SOURCE_KEY = "tv_stats_cpi"
_IDENT = ["source_key", "observation_date", "coicop_code"]
_BASE_PERIOD = "2019Q4=1000"
_DOCLIB_URL = "https://stats.gov.tv/documents-library/"
_RELEASE_HREF_RE = re.compile(
    r'href="(https://stats\.gov\.tv/download/30/consumer-price-index/\d+/[^"]*release-tables[^"]*)"',
    re.IGNORECASE,
)

_COICOP_MAP = {
    "1 FOOD GROUP": "01",
    "1.1 MEAT": "01.1.2",
    "1.2 FISH": "01.1.3",
    "1.3 DAIRY PRODUCE": "01.1.4",
    "1.4 CEREALS": "01.1.1",
    "1.5 SUGAR AND SWEETS": "01.1.8",
    "1.7 BEVERAGES": "01.2",
    "1.8 COOKING OIL & FATS": "01.1.5",
    "1.9 MISCELLANEOUS FOOD": "01.1.9",
    "2 ALCOHOL & TOBACCO GROUP": "02",
    "2.1 ALCOHOL": "02.1",
    "2.2 TOBACCO": "02.2",
    "3 CLOTHING & TEXTILES GROUP": "03",
    "3.1 CLOTHINGS": "03.1",
    "3.2 TEXTILE": "03.1.1",
    "4 TRANSPORT GROUP": "07",
    "4.1 SHIP FARES": "07.3.3",
    "4.2 AIR FARES": "07.3.4",
    "4.4 PRIVATE TRANSPORT": "07.2",
    "5 HOUSING GROUP": "04",
    "5.1 HOUSE RENTAL": "04.1",
    "5.2 HOUSE MAINTENANCE": "04.3",
    "5.3 COOKING FUEL AND ELECTRICITY": "04.5",
    "5.4 HOUSEHOLDS APPLIANCES": "05.3",
    "6.1 EDUCATION": "10",
    "6.2 TELECOM": "08",
    "6.3 ENTERTAINMENT": "09",
    "6.4 TOILETRIES": "12.1",
    "6.5 CLEANING MATERIALS": "05.6",
}

_DROP_LABELS = {
    "Total All Group Expenditure",
    "1.6 VEGETABLES AND FRUITS",
    "6 MISCELLANEOUS GROUP",
    "6.6 MISCELLANEOUS",
}


def _find_latest_xlsx_url(session) -> str | None:
    try:
        resp = session.get(_DOCLIB_URL, timeout=30)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] documents-library fetch failed: %s", _SOURCE_KEY, exc)
        return None
    m = _RELEASE_HREF_RE.search(resp.text)
    return m.group(1) if m else None


def _rows_from_xlsx(xlsx_bytes: bytes, url: str, cutoff: date) -> list[dict]:
    df = pd.read_excel(io.BytesIO(xlsx_bytes), sheet_name="T2", header=None)
    header = df.iloc[3].tolist()
    date_cols = []
    for i, h in enumerate(header):
        if i < 2:
            continue
        ts = pd.to_datetime(h, errors="coerce")
        if pd.notna(ts):
            date_cols.append((i, ts.date()))
    if not date_cols:
        return []

    ts_scrape = get_scrape_ts()
    out: list[dict] = []
    for row_idx in range(4, len(df)):
        raw_label = df.iloc[row_idx, 1]
        if pd.isna(raw_label):
            continue
        label = re.sub(r"\s+", " ", str(raw_label)).strip()
        if label in _DROP_LABELS:
            continue
        coicop = _COICOP_MAP.get(label)
        if coicop is None:
            # Section-header rows ("1. FOOD", ...) carry no data — silent skip.
            # Anything else unmapped is a real gap, worth a warning.
            has_data = any(pd.notna(df.iloc[row_idx, c]) for c, _ in date_cols)
            if has_data:
                logger.warning(
                    "[%s] no COICOP mapping for %r — dropping row", _SOURCE_KEY, label
                )
            continue
        for col_idx, obs_date in date_cols:
            if obs_date <= cutoff:
                continue
            val = df.iloc[row_idx, col_idx]
            if pd.isna(val):
                continue
            try:
                index_value = float(val)
            except (TypeError, ValueError):
                continue
            r = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "quarterly_avg",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": coicop,
                "index_value": round(index_value, 4),
                "index_base_period": _BASE_PERIOD,
                "source_url": url,
                "notes": f"category={label}",
                "scrape_ts": ts_scrape,
                "observation_hash": None,
            }
            r["observation_hash"] = make_hash(r, _IDENT)
            out.append(r)
    return out


def fetch_tv_stats_cpi(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120 Safari/537.36"
        }
    )
    xlsx_url = _find_latest_xlsx_url(session)
    if not xlsx_url:
        logger.warning(
            "[%s] no CPI release-tables link found on documents-library", _SOURCE_KEY
        )
        return None
    try:
        resp = session.get(xlsx_url, timeout=60)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] xlsx fetch failed: %s", _SOURCE_KEY, exc)
        return None
    rows = _rows_from_xlsx(resp.content, xlsx_url, cutoff)
    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
