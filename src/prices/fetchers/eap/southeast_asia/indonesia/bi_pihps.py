"""Bank Indonesia PIHPS Nasional -- daily national average food prices from
the traditional-market (Pasar Tradisional) survey.

https://www.bi.go.id/hargapangan/TabelHarga/PasarTradisionalDaerah is a
DevExtreme (DevExpress ASP.NET MVC) data grid. Its backing routes are
unauthenticated JSON and answer cold to plain `requests` with a browser UA --
no session bootstrap, no APIM key, no WAF (probed 2026-09-11):

  GET /hargapangan/WebSite/TabelHarga/GetRefPriceType
      -> 1 Pasar Tradisional, 2 Pasar Modern, 3 Pedagang Besar, 4 Produsen
  GET /hargapangan/WebSite/TabelHarga/GetRefCommodityAndCategory
      -> 10 categories ("cat_<n>") + 21 commodities ("com_<n>"), each with a
         `denomination` (all "kg" today) and its parent `cat_id`
  GET /hargapangan/WebSite/TabelHarga/GetGridDataDaerah
      ?price_type_id=1&comcat_id=<csv of every cat_/com_ id>
      &province_id=&regency_id=&market_id=&tipe_laporan=1
      &start_date=YYYY-MM-DD&end_date=YYYY-MM-DD

The grid is WIDE: one row per commodity, one column per survey date keyed
"DD/MM/YYYY", values being display strings with thousands separators
("16,350"). Rows carry `level` 1 (the 10 category aggregates) and `level` 2
(the 21 individual commodities); only level 2 is emitted -- the level-1 rows
are averages OF the level-2 rows and would double-count.

Leaving province_id / regency_id / market_id empty yields the NATIONAL
average, which is what this fetcher takes.

History: the series starts mid-2017 (2017-01 returns zero rows, 2017-06
returns 22 date columns), hence fallback_date 2017-01-01. A single call
covering Jan-2025..Sep-2026 returned 443 date columns in one 305 KB response,
so the fetcher walks the window in 365-day chunks rather than per-day.

Prices are IDR per kg. A 2026-09-10 spot check: Beras Kualitas Bawah I
14,750 IDR/kg; the Beras category aggregate 16,350 IDR/kg. Plausible against
published Indonesian rice retail prices -- no minor-unit or 10x scaling.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_BASE = "https://www.bi.go.id/hargapangan"
_PAGE_URL = f"{_BASE}/TabelHarga/PasarTradisionalDaerah"
_REF_URL = f"{_BASE}/WebSite/TabelHarga/GetRefCommodityAndCategory"
_GRID_URL = f"{_BASE}/WebSite/TabelHarga/GetGridDataDaerah"
_COUNTRY = "Indonesia"
_CURRENCY = "IDR"
_SOURCE_KEY = "id_bi_pihps"
_IDENT = ["source_key", "observation_date", "item_name", "unit"]
# price_type_id 1 = Pasar Tradisional; tipe_laporan 1 = Laporan Harian (daily).
_PRICE_TYPE_ID = 1
_REPORT_TYPE_DAILY = 1
_CHUNK_DAYS = 365
_META_KEYS = {"no", "name", "level"}
_HEADERS = {
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Referer": _PAGE_URL,
}


def _parse_price(raw) -> float | None:
    if raw is None:
        return None
    text = str(raw).replace(",", "").strip()
    if not text or text == "-":
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    return value if value > 0 else None


def _parse_col_date(key: str) -> date | None:
    try:
        return datetime.strptime(key, "%d/%m/%Y").date()
    except ValueError:
        return None


def _fetch_ref(session) -> tuple[str, dict[str, str]]:
    """Return (comcat_id csv, {commodity name -> unit})."""
    resp = session.get(_REF_URL, headers=_HEADERS, timeout=60)
    resp.raise_for_status()
    data = resp.json()["data"]
    ids = ",".join(row["id"] for row in data)
    units = {
        row["name"].strip(): (row.get("denomination") or "kg").strip()
        for row in data
        if str(row["id"]).startswith("com_")
    }
    return ids, units


def _fetch_window(session, comcat_ids: str, start: date, end: date) -> list[dict]:
    params = {
        "price_type_id": _PRICE_TYPE_ID,
        "comcat_id": comcat_ids,
        "province_id": "",
        "regency_id": "",
        "market_id": "",
        "tipe_laporan": _REPORT_TYPE_DAILY,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    }
    resp = session.get(_GRID_URL, params=params, headers=_HEADERS, timeout=180)
    resp.raise_for_status()
    return resp.json().get("data") or []


def fetch_id_bi_pihps(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        }
    )

    try:
        comcat_ids, units = _fetch_ref(session)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] commodity reference fetch failed: %s", _SOURCE_KEY, exc)
        return None
    if not comcat_ids:
        logger.warning("[%s] empty commodity reference", _SOURCE_KEY)
        return None

    today = date.today()
    start = cutoff + timedelta(days=1)
    if start > today:
        return None

    ts = get_scrape_ts()
    rows: list[dict] = []
    window_start = start
    while window_start <= today:
        window_end = min(window_start + timedelta(days=_CHUNK_DAYS - 1), today)
        try:
            grid = _fetch_window(session, comcat_ids, window_start, window_end)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[%s] grid fetch %s..%s failed: %s",
                _SOURCE_KEY,
                window_start,
                window_end,
                exc,
            )
            grid = []

        for record in grid:
            # level 1 rows are category aggregates OF the level 2 rows.
            if record.get("level") != 2:
                continue
            item_name = (record.get("name") or "").strip()
            if not item_name:
                continue
            unit = units.get(item_name, "kg")
            for key, raw in record.items():
                if key in _META_KEYS:
                    continue
                obs_date = _parse_col_date(key)
                if obs_date is None or obs_date <= cutoff:
                    continue
                price = _parse_price(raw)
                if price is None:
                    continue
                row = {
                    "observation_date": obs_date.isoformat(),
                    "period_kind": "snapshot",
                    "country": _COUNTRY,
                    "source_key": _SOURCE_KEY,
                    "item_name": item_name,
                    "price_local": price,
                    "currency": _CURRENCY,
                    "unit": unit,
                    "source_url": _PAGE_URL,
                    "scrape_ts": ts,
                    "observation_hash": None,
                }
                row["observation_hash"] = make_hash(row, _IDENT)
                rows.append(row)

        window_start = window_end + timedelta(days=1)

    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
