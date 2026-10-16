"""Parallel-market (unofficial) exchange rates next to the official FX series.

Official rates stay in ``frankfurter`` / ``refresh``. This module keeps a
second, monthly series per currency from the sources that report a real
market rate: WFP VAM (BIF ETB IQD LBP LYD MWK SDG SSP YER), World Bank RTFX
where its "unofficial" column is not the official rate (SOS SSP LBP), the
Argentine blue dollar, Venezuela's paralelo and Bolivia's USDT rate. It is
shared by fuel and prices; ``load_parallel`` reads the cache and pipelines
attach it themselves (fuel: ``fuel.fx_parallel.attach_parallel``).
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

import pandas as pd

from core.http import make_session

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
# Shared by fuel and prices.
PARALLEL_CACHE = _PROJECT_ROOT / "data" / "fx" / "parallel.csv"
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
    frames = (
        _vam_series(session)
        + frames
        + _market_series(session, cache_path)
        + _portal_series(session, cache_path)
    )
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


_IRR_URL = "https://api.tgju.org/v1/market/indicator/summary-table-data/price_dollar_rl"
_ETB_URL = "https://ethioblackmarket.com/api/price-history-range"
_SYP_URL = "https://sp-today.com/en/currency/us_dollar"
SOURCE_IRR = "tgju:price_dollar_rl:close-monthly-median"
SOURCE_ETB = "ethioblackmarket:usd-monthly"
SOURCE_SYP = "sp-today:damascus-buy"


def _monthly(dates, rates, currency, iso3, source) -> pd.DataFrame:
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(dates).dt.to_period("M").dt.to_timestamp(),
            "rate": pd.to_numeric(rates, errors="coerce"),
        }
    ).dropna()
    monthly = df.groupby("date").agg(
        rate_usd_to_local=("rate", "median"), markets=("rate", "size")
    )
    return monthly.reset_index().assign(currency=currency, iso3=iso3, source=source)


def _portal_series(session, cache_path: Path) -> list[pd.DataFrame]:
    """Parallel rates from market portals: Iran's free-market dollar (tgju,
    daily since 2011, rial), Ethiopia's black-market rate (ethioblackmarket,
    monthly since 2023, Binance-P2P based; fills months after WFP VAM ends) and
    Syria's Damascus rate (sp-today page, current value only, new pound =
    old / 100; earlier months carried over from the cache)."""
    out: list[pd.DataFrame] = []
    try:
        rows = session.get(_IRR_URL, params={"start": 0, "length": 10000}, timeout=120)
        rows = rows.json()["data"]
        out.append(
            _monthly(
                pd.Series([r[6] for r in rows]).str.replace("/", "-"),
                pd.Series([r[3] for r in rows]).str.replace(",", ""),
                "IRR",
                "IRN",
                SOURCE_IRR,
            )
        )
    except Exception as exc:
        logger.warning("IRR parallel fetch failed: %s", exc)
    try:
        months = session.get(_ETB_URL, timeout=60).json()["monthlyPrices"]
        out.append(
            _monthly(
                pd.Series([m["month"] + "-01" for m in months]),
                pd.Series([m["value"].get("USD") for m in months]),
                "ETB",
                "ETH",
                SOURCE_ETB,
            )
        )
    except Exception as exc:
        logger.warning("ETB parallel fetch failed: %s", exc)
    previous = load_parallel(cache_path)
    syp = previous[previous["source"].eq(SOURCE_SYP)]
    try:
        page = session.get(_SYP_URL, timeout=60).text
        old_pounds = re.search(r'\\"damascus\\":\{\\"buy\\":(\d+)', page).group(1)
        month = (
            pd.Timestamp.now(tz="UTC").tz_localize(None).to_period("M").to_timestamp()
        )
        syp = pd.concat(
            [
                syp[syp["date"] != month],
                pd.DataFrame(
                    [
                        {
                            "date": month,
                            "rate_usd_to_local": float(old_pounds) / 100,
                            "markets": 1,
                            "currency": "SYP",
                            "iso3": "SYR",
                            "source": SOURCE_SYP,
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
    except Exception as exc:
        logger.warning("SYP parallel fetch failed: %s", exc)
    if not syp.empty:
        out.append(syp)
    return out


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
