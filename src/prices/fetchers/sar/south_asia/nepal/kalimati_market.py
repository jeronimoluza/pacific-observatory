"""Kalimati Fruits and Vegetable Market Development Board (Nepal) — wholesale.

Nepal's largest wholesale market publishes daily min/max/avg prices for ~100
commodities via a small CSRF handshake: GET /price for a `_token` + session
cookie, then POST the same URL with `_token` + `datePricing=YYYY-MM-DD`.
Re-verified live 2026-08-06: GET -> 200 with `_token`; POST with today's date
-> 200, ~31KB HTML fragment/table, e.g. 'गोलभेडा ठूलो(नेपाली)' (tomato,
large, local), unit 'के.जी.' (kg), min रू ५०.००, max रू ६०.००, avg रू ५५.००.

Prices are rendered with Devanagari digits (० - ९), not ASCII, so they are
translated before parsing. Since the site is a walkable daily archive, this
fetcher requests one day per call, walking backward from today until it
either hits `cutoff` or a day with no table rows (market closed).
"""

from __future__ import annotations

import logging
import re
from datetime import date, timedelta

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_PRICE_PAGE = "https://kalimatimarket.gov.np/price"
_COUNTRY = "Nepal"
_CURRENCY = "NPR"
_SOURCE_KEY = "np_kalimati_market"
_IDENT = ["source_key", "observation_date", "item_name", "unit"]
_MAX_DAYS_BACK = 30
_TOKEN_RE = re.compile(r'name="_token" value="([^"]+)"')
_ROW_RE = re.compile(
    r"<td>([^<]+)</td>\s*<td>([^<]+)</td>\s*<td>रू\s*([०-९.,]+)</td>\s*"
    r"<td>रू\s*([०-९.,]+)</td>\s*<td>रू\s*([०-९.,]+)</td>",
)

_DEV_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def _num(text: str) -> float | None:
    try:
        return float(text.translate(_DEV_DIGITS).replace(",", ""))
    except ValueError:
        return None


def _fetch_token(session):
    r = session.get(_PRICE_PAGE, timeout=30)
    r.raise_for_status()
    m = _TOKEN_RE.search(r.text)
    if not m:
        return None
    return m.group(1)


def _fetch_day(session, token: str, day: date, cutoff: date) -> list[dict]:
    if day <= cutoff:
        return []
    try:
        r = session.post(
            _PRICE_PAGE,
            data={"_token": token, "datePricing": day.isoformat()},
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Referer": _PRICE_PAGE,
            },
            timeout=30,
        )
        r.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] POST failed for %s: %s", _SOURCE_KEY, day, exc)
        return []
    rows = _ROW_RE.findall(r.text)
    if not rows:
        return []
    ts = get_scrape_ts()
    out: list[dict] = []
    for name, unit, lo_txt, hi_txt, avg_txt in rows:
        avg = _num(avg_txt)
        if avg is None or avg <= 0:
            continue
        lo = _num(lo_txt)
        hi = _num(hi_txt)
        row = {
            "observation_date": day.isoformat(),
            "period_kind": "daily",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": name.strip(),
            "price_local": round(avg, 2),
            "currency": _CURRENCY,
            "unit": unit.strip(),
            "source_url": _PRICE_PAGE,
            "notes": f"min={lo}; max={hi}",
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        out.append(row)
    return out


def fetch_np_kalimati_market(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    token = _fetch_token(session)
    if not token:
        logger.warning("[%s] could not obtain CSRF token", _SOURCE_KEY)
        return None
    today = date.today()
    all_rows: list[dict] = []
    for i in range(_MAX_DAYS_BACK):
        day = today - timedelta(days=i)
        if day <= cutoff:
            break
        day_rows = _fetch_day(session, token, day, cutoff)
        if not day_rows:
            continue
        all_rows.extend(day_rows)
    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(all_rows), cutoff)
    return pd.DataFrame(all_rows) if all_rows else None
