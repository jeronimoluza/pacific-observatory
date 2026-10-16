"""Parallel-market (unofficial) exchange rates next to the official FX series.

USD prices stay on the official rate (``fx.py``). This module keeps a second,
monthly series from the World Bank Real-Time Exchange Rates panel (RTFX): the
median across a country's markets of ``c_exchange_rate_unofficial`` (local
units per USD). Build attaches it as ``fx_rate_parallel`` /
``price_usd_parallel``; publish shows both.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pandas as pd

from core.http import make_session

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
PARALLEL_CACHE = _PROJECT_ROOT / "data" / "fuel" / "fx_parallel.csv"
_API_URL = (
    "https://microdata.worldbank.org/index.php/api/tables/data/FCV/WLD_2023_RTFX_v01_M"
)
_FIELDS = "ISO3,price_date,currency,c_exchange_rate_unofficial"
_PAGE = 10000
SOURCE = "wb_rtfx:c_exchange_rate_unofficial:market-median"
# A monthly parallel rate is carried to later days for at most this long.
MAX_CARRY = pd.Timedelta(days=92)
_COLUMNS = ["currency", "date", "rate_usd_to_local", "iso3", "markets", "source"]


def _fetch_country(session, iso3: str) -> pd.DataFrame:
    frames, offset = [], 0
    while True:
        resp = session.get(
            _API_URL,
            params={"ISO3": iso3, "fields": _FIELDS, "limit": _PAGE, "offset": offset},
            timeout=120,
        )
        resp.raise_for_status()
        payload = resp.json()
        rows = payload.get("data") or []
        frames.append(pd.DataFrame(rows))
        offset += len(rows)
        if not rows or offset >= int(payload.get("found") or 0):
            break
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def refresh_parallel_cache(cache_path: Path = PARALLEL_CACHE) -> int:
    """Rebuild the cache from every provider; return rows written. Covers all
    currencies with a usable parallel series, not only the fuel countries."""
    session = make_session()
    frames = []
    for iso3, currency in sorted(RTFX_PARALLEL.items()):
        if currency == "USD":
            continue
        try:
            raw = _fetch_country(session, iso3)
        except Exception as exc:
            logger.warning("RTFX fetch failed for %s: %s", iso3, exc)
            continue
        if raw.empty:
            continue
        raw = raw[raw["currency"].astype(str).str.upper() == currency]
        rate = pd.to_numeric(raw["c_exchange_rate_unofficial"], errors="coerce")
        raw = raw.assign(
            rate=rate, month=pd.to_datetime(raw["price_date"], errors="coerce")
        )
        raw = raw[raw["rate"].gt(0) & raw["month"].notna()]
        if raw.empty:
            continue
        monthly = raw.groupby("month").agg(
            rate_usd_to_local=("rate", "median"), markets=("rate", "size")
        )
        frames.append(
            monthly.reset_index()
            .rename(columns={"month": "date"})
            .assign(currency=currency, iso3=iso3, source=SOURCE)
        )
    if not frames:
        logger.warning("RTFX: no parallel rates fetched; cache left as is")
        return 0
    # WFP VAM first, RTFX only for the months VAM does not cover (ETB after
    # 2025-06, SSP gaps).
    frames = _vam_series(session) + frames + _market_series(session, cache_path)
    out = (
        pd.concat(frames, ignore_index=True)[_COLUMNS]
        .drop_duplicates(subset=["currency", "date"], keep="first")
        .sort_values(["currency", "date"])
    )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache_path.with_name(f"{cache_path.name}.{os.getpid()}.tmp")
    out.to_csv(tmp, index=False, date_format="%Y-%m-%d")
    os.replace(tmp, cache_path)
    logger.info(
        "Parallel FX rates: %d rows for %s -> %s",
        len(out),
        ", ".join(sorted(out["currency"].unique())),
        cache_path,
    )
    return len(out)


# RTFX's "unofficial" column matches the official rate (within ~2%) for all
# of its 37 countries except these (checked 2026-10-16; e.g. MMK sits on the
# CBM reference 2,100 while the CBM market trading rate is ~3,660, MWK 1,757
# vs ~4,000), so it is used only here. SSP months WFP VAM covers take VAM's.
RTFX_PARALLEL = {"SOM": "SOS", "SSD": "SSP", "LBN": "LBP"}

# WFP VAM Economic Explorer: monthly unofficial (market) rate, public API.
_VAM_URL = (
    "https://api.vam.wfp.org/economicExplorer/Currency/GetMonthlyUnofficialExchangeRate"
)
VAM_CURRENCIES = {
    "BIF": "BDI",
    "ETB": "ETH",
    "IQD": "IRQ",
    "LBP": "LBN",
    "LYD": "LBY",
    "MWK": "MWI",
    "SDG": "SDN",
    "SSP": "SSD",
    "YER": "YEM",
}
SOURCE_VAM = "wfp_vam:unofficial-monthly"


def _vam_series(session) -> list[pd.DataFrame]:
    """WFP VAM monthly market rates; they replace RTFX where both exist. YER is
    the Aden (government-area) rate."""
    out = []
    for currency, iso3 in VAM_CURRENCIES.items():
        try:
            data = session.get(
                _VAM_URL, params={"currencyCode": currency}, timeout=60
            ).json()
        except Exception as exc:
            logger.warning("WFP VAM fetch failed for %s: %s", currency, exc)
            continue
        values = data.get("values") or []
        if not values:
            continue
        start = pd.Timestamp(year=data["startYear"], month=data["startMonth"], day=1)
        df = pd.DataFrame(
            {
                "date": pd.date_range(start, periods=len(values), freq="MS"),
                "rate_usd_to_local": pd.to_numeric(pd.Series(values), errors="coerce"),
            }
        ).dropna()
        out.append(
            df.assign(markets=pd.NA, currency=currency, iso3=iso3, source=SOURCE_VAM)
        )
    return out


_VES_URL = "https://ve.dolarapi.com/v1/historicos/dolares"
SOURCE_VES = "dolarapi-ve:paralelo:monthly-median"
_ARS_BLUE_URL = "https://api.argentinadatos.com/v1/cotizaciones/dolares/blue"
_BOB_URL = "https://bo.dolarapi.com/v1/dolares"
SOURCE_ARS = "argentinadatos:dolar-blue:venta-monthly-median"
SOURCE_BOB = "dolarapi-bo:binance:venta"


def _market_series(session, cache_path: Path) -> list[pd.DataFrame]:
    """Parallel rates outside RTFX and VAM: Argentina's blue dollar (daily
    since 2011) and Venezuela's paralelo (daily since 2026-02), both as monthly
    medians, and Bolivia's USDT/Binance rate (current value only, so earlier
    months are carried over from the existing cache)."""
    out: list[pd.DataFrame] = []
    try:
        daily = pd.DataFrame(session.get(_ARS_BLUE_URL, timeout=60).json())
        daily = daily.assign(
            date=pd.to_datetime(daily["fecha"]).dt.to_period("M").dt.to_timestamp(),
            rate=pd.to_numeric(daily["venta"], errors="coerce"),
        ).dropna(subset=["rate"])
        monthly = daily.groupby("date").agg(
            rate_usd_to_local=("rate", "median"), markets=("rate", "size")
        )
        out.append(
            monthly.reset_index().assign(currency="ARS", iso3="ARG", source=SOURCE_ARS)
        )
    except Exception as exc:
        logger.warning("ARS blue fetch failed: %s", exc)
    try:
        hist = pd.DataFrame(session.get(_VES_URL, timeout=60).json())
        hist = hist[hist["fuente"].eq("paralelo")].assign(
            date=lambda d: (
                pd.to_datetime(d["fecha"]).dt.to_period("M").dt.to_timestamp()
            ),
            rate=lambda d: pd.to_numeric(d["promedio"], errors="coerce"),
        )
        monthly = (
            hist.dropna(subset=["rate"])
            .groupby("date")
            .agg(rate_usd_to_local=("rate", "median"), markets=("rate", "size"))
        )
        out.append(
            monthly.reset_index().assign(currency="VES", iso3="VEN", source=SOURCE_VES)
        )
    except Exception as exc:
        logger.warning("VES parallel fetch failed: %s", exc)
    previous = load_parallel(cache_path)
    bob = previous[previous["source"].eq(SOURCE_BOB)]
    try:
        quotes = session.get(_BOB_URL, timeout=60).json()
        quote = next(q for q in quotes if q.get("casa") == "binance")
        month = (
            pd.Timestamp.now(tz="UTC").tz_localize(None).to_period("M").to_timestamp()
        )
        bob = pd.concat(
            [
                bob[bob["date"] != month],
                pd.DataFrame(
                    [
                        {
                            "date": month,
                            "rate_usd_to_local": float(quote["venta"]),
                            "markets": 1,
                            "currency": "BOB",
                            "iso3": "BOL",
                            "source": SOURCE_BOB,
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
    except Exception as exc:
        logger.warning("BOB parallel fetch failed: %s", exc)
    if not bob.empty:
        out.append(bob)
    return out


def load_parallel(cache_path: Path = PARALLEL_CACHE) -> pd.DataFrame:
    if not cache_path.exists():
        return pd.DataFrame(columns=_COLUMNS)
    df = pd.read_csv(cache_path)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df.dropna(subset=["date", "rate_usd_to_local"])


def attach_parallel(
    df: pd.DataFrame, cache_path: Path = PARALLEL_CACHE
) -> pd.DataFrame:
    """Add ``fx_rate_parallel`` and ``price_usd_parallel`` (NaN where none applies)."""
    out = df.copy()
    out["fx_rate_parallel"] = float("nan")
    rates = load_parallel(cache_path)
    if out.empty or rates.empty:
        out["price_usd_parallel"] = float("nan")
        return out
    dates = pd.to_datetime(out["observation_date"], errors="coerce")
    for currency, group in rates.groupby("currency"):
        mask = out["currency"].eq(currency) & dates.notna()
        if not mask.any():
            continue
        left = pd.DataFrame({"date": dates[mask], "_i": out.index[mask]}).sort_values(
            "date"
        )
        matched = pd.merge_asof(
            left,
            group[["date", "rate_usd_to_local"]].sort_values("date"),
            on="date",
            direction="backward",
            tolerance=MAX_CARRY,
        )
        out.loc[matched["_i"], "fx_rate_parallel"] = matched[
            "rate_usd_to_local"
        ].to_numpy()
    out["price_usd_parallel"] = (
        pd.to_numeric(out["price_local"], errors="coerce") / out["fx_rate_parallel"]
    )
    return out
