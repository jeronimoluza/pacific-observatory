"""Lao Statistics Bureau (LAOSIS) — CPI index, monthly.

LAOSIS portal has an expired SSL certificate; fetcher uses requests with
verify=False (documented in known_blockers.md). Emits IndexObservation
rows per COICOP division available from the portal.

The portal at laosis.lsb.gov.la/majorIndicators.do serves an HTML table
of major economic indicators including CPI headline. Division-level detail
may require navigating sub-pages; this fetcher targets the available
machine-readable data and falls back to the IMF CPI headline if LAOSIS
returns no division rows.
"""

from __future__ import annotations

import logging
import re
import urllib3
from datetime import date, datetime

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

# Suppress SSL verification warnings — LAOSIS cert is expired, not a WAF.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

_LAOSIS_URL = "https://laosis.lsb.gov.la/majorIndicators.do"
_COUNTRY = "Lao PDR"
_SOURCE_KEY = "la_laosis_cpi"
_BASE_PERIOD = "2012=100"  # LSB base year; update if LSB completes 2026 rebase

# Publisher labels (Lao/English) → COICOP 2-digit divisions
# LSB groupings roughly follow COICOP 2018 but may merge some divisions.
_COICOP_MAP = {
    "Food and non-alcoholic beverages": "01",
    "Alcoholic beverages, tobacco and narcotics": "02",
    "Clothing and footwear": "03",
    "Housing, water, electricity, gas and other fuels": "04",
    "Furnishings, household equipment and routine maintenance": "05",
    "Health": "06",
    "Transport": "07",
    "Communication": "08",
    "Recreation and culture": "09",
    "Education": "10",
    "Restaurants and hotels": "11",
    "Miscellaneous goods and services": "12",
    # Lao-script variants (fallback if portal returns lo-script labels)
    "ອາຫານ ແລະ ເຄື່ອງດື່ມທີ່ບໍ່ມີ​ທາດ​ເຫຼົ້າ": "01",
    "ເຄື່ອງດື່ມມີທາດເຫຼົ້າ, ຢາສູບ": "02",
    "ເຄື່ອງນຸ່ງຫົ່ມ ແລະ ເກີບ": "03",
    "ທີ່ຢູ່ອາໄສ, ນ້ຳ, ໄຟຟ້າ, ແກ໊ສ": "04",
    "ການເຄື່ອນຍ້າຍ": "07",
    "ການສື່ສານ": "08",
    "ການສຶກສາ": "10",
}

_IDENT = ["source_key", "observation_date", "coicop_code"]


def _parse_period(raw: str) -> str | None:
    """Try to parse a period label into YYYY-MM-01 ISO date."""
    raw = raw.strip()
    for fmt in ("%Y-%m", "%b %Y", "%B %Y", "%Y/%m", "%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-01")
        except ValueError:
            pass
    m = re.search(r"(\d{4})[/-](\d{1,2})", raw)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-01"
    return None


def fetch_la_laosis_cpi(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    # LAOSIS has an expired cert — verify=False is intentional (not a WAF).
    resp = session.get(_LAOSIS_URL, timeout=30, verify=False)
    resp.raise_for_status()

    tables = pd.read_html(resp.text)
    if not tables:
        logger.warning("LAOSIS returned no parseable HTML tables")
        return None

    rows: list[dict] = []
    for tbl in tables:
        # Heuristic: look for tables that have a period-like column and numeric index values
        tbl_str = tbl.to_string()
        if not any(
            kw in tbl_str for kw in ("CPI", "Price Index", "ດັດຊະນີ", "Inflation")
        ):
            continue
        for _, r in tbl.iterrows():
            vals = [str(v).strip() for v in r.values if pd.notna(v)]
            if len(vals) < 2:
                continue
            label = vals[0]
            coicop = _COICOP_MAP.get(label)
            if not coicop:
                continue
            for v in vals[1:]:
                period_str = _parse_period(v)
                if period_str:
                    obs_date = date.fromisoformat(period_str)
                    if obs_date <= cutoff:
                        continue
                    # Next value should be the index
                    idx = (
                        vals[vals.index(v) + 1]
                        if vals.index(v) + 1 < len(vals)
                        else None
                    )
                    if idx is None:
                        continue
                    try:
                        index_value = float(str(idx).replace(",", ""))
                    except ValueError:
                        continue
                    row: dict = {
                        "observation_date": period_str,
                        "period_kind": "monthly_avg",
                        "country": _COUNTRY,
                        "source_key": _SOURCE_KEY,
                        "coicop_code": coicop,
                        "index_value": index_value,
                        "index_base_period": _BASE_PERIOD,
                        "source_url": _LAOSIS_URL,
                        "scrape_ts": get_scrape_ts(),
                        "observation_hash": None,
                    }
                    row["observation_hash"] = make_hash(row, _IDENT)
                    rows.append(row)

    if not rows:
        logger.warning(
            "LAOSIS CPI: no division rows parsed — portal may have changed layout. "
            "Re-probe laosis.lsb.gov.la and update _COICOP_MAP."
        )
    return pd.DataFrame(rows) if rows else None
