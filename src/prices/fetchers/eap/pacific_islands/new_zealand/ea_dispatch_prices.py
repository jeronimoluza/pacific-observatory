"""New Zealand Electricity Authority dispatch energy prices."""

from __future__ import annotations

import io
import logging
from datetime import date, timedelta

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "New Zealand"
_CURRENCY = "NZD"
_SOURCE_KEY = "nz_ea_dispatch_prices"
_COICOP = "04.5.1"
_UNIT = "MWh"
_IDENT = ["source_key", "observation_date", "point_of_connection", "trading_period"]
_BASE = "https://www.emi.ea.govt.nz/Wholesale/Datasets/DispatchAndPricing/DispatchEnergyPrices"
_MAX_LOOKBACK_DAYS = 21
_MAX_ROWS = 100


def _candidate_urls(today: date):
    for delta in range(_MAX_LOOKBACK_DAYS + 1):
        day = today - timedelta(days=delta)
        stamp = day.strftime("%Y%m%d")
        yield day, f"{_BASE}/{day:%Y}/{stamp}_DispatchEnergyPrices.csv"


def _latest_csv(session) -> tuple[date, str, pd.DataFrame] | None:
    for trading_date, url in _candidate_urls(date.today()):
        try:
            resp = session.get(url, timeout=60)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] fetch failed for %s: %s", _SOURCE_KEY, url, exc)
            continue
        if resp.status_code != 200 or not resp.text.startswith("TradingDate,"):
            continue
        df = pd.read_csv(io.StringIO(resp.text))
        return trading_date, url, df
    return None


def fetch_nz_ea_dispatch_prices(cutoff: date) -> pd.DataFrame | None:
    session = get_session(retries=1)
    latest = _latest_csv(session)
    if latest is None:
        logger.warning("[%s] no recent dispatch-energy CSV found", _SOURCE_KEY)
        return None

    trading_date, url, df = latest
    if trading_date <= cutoff:
        return None

    needed = {
        "TradingDate",
        "TradingPeriod",
        "PointOfConnection",
        "Island",
        "IsProxyPriceFlag",
        "DollarsPerMegawattHour",
    }
    if not needed.issubset(df.columns):
        logger.warning("[%s] missing expected columns from %s", _SOURCE_KEY, url)
        return None

    sample = (
        df[df["IsProxyPriceFlag"].astype(str).str.upper().eq("N")]
        .assign(
            _publish_dt=lambda x: pd.to_datetime(
                x["PublishDateTime"], errors="coerce", utc=True
            )
        )
        .sort_values("_publish_dt")
        .drop_duplicates(
            ["TradingDate", "TradingPeriod", "PointOfConnection"], keep="last"
        )
        .sort_values(["TradingPeriod", "PointOfConnection"])
        .head(_MAX_ROWS)
    )
    ts = get_scrape_ts()
    rows: list[dict] = []
    for rec in sample.to_dict("records"):
        poc = str(rec["PointOfConnection"]).strip()
        period = int(rec["TradingPeriod"])
        price = float(rec["DollarsPerMegawattHour"])
        row = {
            "observation_date": trading_date.isoformat(),
            "period_kind": "half_hour",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP,
            "item_name": f"Wholesale electricity dispatch price, {poc}, trading period {period}",
            "price_local": price,
            "currency": _CURRENCY,
            "unit": _UNIT,
            "source_url": url,
            "notes": f"Electricity Authority EMI dispatch energy price; island={rec.get('Island') or 'na'}",
            "scrape_ts": ts,
            "point_of_connection": poc,
            "trading_period": period,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        row.pop("point_of_connection")
        row.pop("trading_period")
        rows.append(row)

    logger.info("[%s] %d rows from %s", _SOURCE_KEY, len(rows), url)
    return pd.DataFrame(rows) if rows else None
