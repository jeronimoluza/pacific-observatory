"""South Korea — KEPCO (Korea Electric Power Corporation) household tariff.

KEPCO publishes its residential electricity tariff schedule as a plain,
server-rendered HTML table (no JS, no auth) at:

  https://home.kepco.co.kr/kepco/front/html/CY/E/E/CYEEHP00101.html

Verified live 2026-09-06: `pandas.read_html` parses two 6-tier tables straight
off the page -- 저압 (low-voltage residential, table index 1) and 고압
(high-voltage residential, table index 2) -- each carrying a basic monthly fee
(기본요금, KRW/household) and a per-kWh energy charge (전력량 요금, KRW/kWh)
per usage band. Each table is preceded by its own "적용일자" (effective-date)
stamp in the surrounding HTML, extracted separately so a genuine KEPCO rate
revision is picked up automatically without a hardcoded decision table (unlike
the Vietnam EVN tariff fetcher, which had to hardcode values from a scanned
PDF -- this source is live HTML every run).

Only the two residential ("주택용 전력") schedules are emitted; the page also
links out to commercial/industrial ("일반용"/"산업용") schedules under
separate URLs, which are out of scope for a household PPP basket.

Single COICOP class (electricity) -> COICOP 04.5.1.0 leaf, narrow source,
short-circuits the classifier.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from io import StringIO

import pandas as pd
from curl_cffi import requests as curl_requests

from prices.fetchers.utils import get_scrape_ts, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Korea, Rep."
_CURRENCY = "KRW"
_SOURCE_KEY = "kepco_kr_tariff"
_SOURCE_URL = "https://home.kepco.co.kr/kepco/front/html/CY/E/E/CYEEHP00101.html"
_UNIT = "kWh"
_COICOP = "04.5.1.0"
_IDENT = ["source_key", "observation_date", "item_name"]

_TABLES = [
    (1, "저압 (Low-voltage residential)"),
    (2, "고압 (High-voltage residential)"),
]

_DATE_RE = re.compile(r"적용일자\s*:\s*(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일")


def _effective_dates(html: str) -> list[date]:
    """First two '적용일자' stamps that precede the 저압/고압 tables (the
    third match on the page, '월 최저요금' minimum-fee note, is skipped by
    only taking the 1st and 3rd occurrences)."""
    matches = _DATE_RE.findall(html)
    picks = []
    for idx in (0, 2):
        if idx < len(matches):
            y, m, d = matches[idx]
            try:
                picks.append(date(int(y), int(m), int(d)))
            except ValueError:
                picks.append(None)
        else:
            picks.append(None)
    return picks


def fetch_kepco_kr_tariff(cutoff: date) -> pd.DataFrame | None:
    resp = curl_requests.get(_SOURCE_URL, impersonate="chrome124", timeout=30)
    resp.raise_for_status()
    html = resp.text

    try:
        tables = pd.read_html(StringIO(html))
    except ValueError as exc:
        logger.warning("[%s] no tables found: %s", _SOURCE_KEY, exc)
        return None

    eff_dates = _effective_dates(html)
    scrape_ts = get_scrape_ts()
    rows: list[dict] = []

    for (table_idx, label), eff_date in zip(_TABLES, eff_dates):
        if eff_date is None or eff_date <= cutoff:
            continue
        if table_idx >= len(tables):
            continue
        df = tables[table_idx]
        if df.shape[1] < 4:
            continue
        for _, r in df.iterrows():
            band = str(r.iloc[0]).strip()
            try:
                basic_fee = float(str(r.iloc[1]).replace(",", ""))
                per_kwh = float(str(r.iloc[3]).replace(",", ""))
            except (ValueError, TypeError):
                continue
            if not band or band.lower() == "nan":
                continue

            # Basic (per-household) fee row
            row_basic = {
                "observation_date": eff_date.isoformat(),
                "period_kind": "effective_from",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": _COICOP,
                "item_name": f"KEPCO {label}, {band}, basic monthly fee",
                "price_local": basic_fee,
                "currency": _CURRENCY,
                "unit": "household/month",
                "source_url": _SOURCE_URL,
                "notes": f"KEPCO residential tariff, {label}, usage band '{band}'.",
                "scrape_ts": scrape_ts,
                "observation_hash": None,
            }
            row_basic["observation_hash"] = make_hash(row_basic, _IDENT)
            rows.append(row_basic)

            # Per-kWh energy-charge row
            row_energy = {
                "observation_date": eff_date.isoformat(),
                "period_kind": "effective_from",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": _COICOP,
                "item_name": f"KEPCO {label}, {band}, energy charge",
                "price_local": per_kwh,
                "currency": _CURRENCY,
                "unit": _UNIT,
                "source_url": _SOURCE_URL,
                "notes": f"KEPCO residential tariff, {label}, usage band '{band}'.",
                "scrape_ts": scrape_ts,
                "observation_hash": None,
            }
            row_energy["observation_hash"] = make_hash(row_energy, _IDENT)
            rows.append(row_energy)

    if not rows:
        logger.info(
            "[%s] all effective dates <= cutoff %s -- nothing new",
            _SOURCE_KEY,
            cutoff,
        )
        return None

    return pd.DataFrame(rows)
