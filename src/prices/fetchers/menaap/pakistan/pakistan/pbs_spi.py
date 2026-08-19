"""Pakistan Bureau of Statistics — Weekly Sensitive Price Indicator (SPI).

Consumer prices of 51 essential items (food + non-food) across 17 cities,
published weekly. The vanity URL https://www.pbs.gov.pk/spi 404s; each week's
bulletin instead lives at a dated WordPress page
https://www.pbs.gov.pk/weekly-sensitive-price-indicator-spi-for-the-week-ended-on-DD-MM-YYYY/
which links to a stable-pattern Annex XLSX
(wp-content/uploads/2020/07/Annex_DD.MM.YYYY.xlsx). Re-verified live
2026-08-06: the week-ended-30-07-2026 bulletin page -> 200, links to
Annex_30.07.2026.xlsx -> 200, 55.8KB, sheet 'Appendix-A' /
'CONSUMER PRICES OF ESSENTIAL ITEMS', MIN/AVG/MAX per item across 7+ cities.
Sample: 'Wheat Flour Bag', '20 Kg', Islamabad AVG PKR 3085.42.

There is no index page that reliably lists the current week (the WordPress
"publication" archive redirects to an old post), so this fetcher discovers
the latest bulletin by trying successive Thursdays going backward from
today until a page resolves.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date, timedelta

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Pakistan"
_CURRENCY = "PKR"
_SOURCE_KEY = "pk_pbs_spi"
_IDENT = ["source_key", "observation_date", "item_name", "unit", "notes"]
_MAX_WEEKS_BACK = 8
_ANNEX_RE = re.compile(r'href="([^"]*Annex_[0-9.]+\.xlsx)"')


def _candidate_dates(today: date) -> list[date]:
    # SPI weeks end on Thursday; probe the most recent ~8 Thursdays.
    days_since_thursday = (today.weekday() - 3) % 7
    last_thursday = today - timedelta(days=days_since_thursday)
    return [last_thursday - timedelta(weeks=i) for i in range(_MAX_WEEKS_BACK)]


def _find_latest_bulletin(session) -> tuple[str, str] | None:
    for d in _candidate_dates(date.today()):
        page_url = (
            "https://www.pbs.gov.pk/weekly-sensitive-price-indicator-spi-for-the-week-ended-on-"
            f"{d.strftime('%d-%m-%Y')}/"
        )
        try:
            r = session.get(page_url, timeout=30)
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "[%s] bulletin probe failed %s: %s", _SOURCE_KEY, page_url, exc
            )
            continue
        if r.status_code != 200:
            continue
        m = _ANNEX_RE.search(r.text)
        if not m:
            continue
        return page_url, m.group(1)
    return None


def _rows(xlsx_bytes: bytes, page_url: str, obs_date: date, cutoff: date) -> list[dict]:
    if obs_date <= cutoff:
        return []
    wb = pd.read_excel(io.BytesIO(xlsx_bytes), sheet_name="Appendix-A", header=None)
    out: list[dict] = []
    ts = get_scrape_ts()
    # City header appears in row index 2 (0-based); MIN/AVG/MAX triples start at col 3.
    city_row = wb.iloc[2].tolist()
    cities = []
    col = 3
    while col < len(city_row) - 1:
        city = str(city_row[col]).strip()
        if city and city.lower() != "nan":
            cities.append((city, col))
        col += 3
    for _, r in wb.iloc[6:].iterrows():
        item = r.get(1)
        unit = r.get(2)
        if not isinstance(item, str) or not item.strip():
            continue
        item = item.strip()
        unit = str(unit).strip() if isinstance(unit, str) else ""
        for city, col in cities:
            try:
                avg = float(r.get(col + 1))
            except (TypeError, ValueError):
                continue
            if not 0 < avg < 1_000_000:
                continue
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "weekly",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "item_name": item,
                "price_local": round(avg, 2),
                "currency": _CURRENCY,
                "unit": unit or None,
                "source_url": page_url,
                "notes": f"city={city}",
                "scrape_ts": ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            out.append(row)
    return out


def fetch_pk_pbs_spi(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    found = _find_latest_bulletin(session)
    if not found:
        logger.warning("[%s] no bulletin resolved within lookback window", _SOURCE_KEY)
        return None
    page_url, annex_href = found
    annex_url = (
        annex_href
        if annex_href.startswith("http")
        else f"https://www.pbs.gov.pk{annex_href}"
    )
    m = re.search(r"Annex_(\d{2})\.(\d{2})\.(\d{4})\.xlsx", annex_url)
    if not m:
        logger.warning(
            "[%s] could not parse date from annex url %s", _SOURCE_KEY, annex_url
        )
        return None
    obs_date = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    try:
        resp = session.get(annex_url, timeout=60)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] annex fetch failed: %s", _SOURCE_KEY, exc)
        return None
    rows = _rows(resp.content, page_url, obs_date, cutoff)
    logger.info(
        "[%s] %d rows (cutoff=%s, obs_date=%s)",
        _SOURCE_KEY,
        len(rows),
        cutoff,
        obs_date,
    )
    return pd.DataFrame(rows) if rows else None
