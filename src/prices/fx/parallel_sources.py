"""More parallel-market FX providers for ``prices.fx.parallel``.

- MMK: Central Bank of Myanmar "FX Market Data" xlsx, bank-customer weighted
  average rate (the market trading rate, vs the 2,100 reference), daily since
  2016, stored as the monthly median.
- DZD (devisesquare.com, Square Port-Said buy rate), ZWG (zimpricecheck.com,
  informal-sector rate, mean of the two quotes) and MVR (adhadhu.com dollar
  rate): portal pages with only today's value, appended month by month.
- MZN, GNF, TND, TTD: Binance P2P USDT ads (median of the top 10 BUY ads, SELL
  when there are none),
  appended month by month. Source tag ``p2p``: a USDT price carries a base
  premium of +2-5% even where no parallel market exists (MAD, XAF, TRY), so
  read it as an upper bound, not a street rate.
"""

from __future__ import annotations

import io
import logging
import re
import statistics
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_CBM_PAGE = "https://www.cbm.gov.mm/foreign-exchange-market"
SOURCE_MMK = "cbm:bank-customer-war:monthly-median"
_PORTALS = {
    # currency: (iso3, url, regex over page text or html, source tag)
    "DZD": (
        "DZA",
        "https://devisesquare.com/",
        r"1 US DOLLAR\s*(\d+)\s*\.\s*(\d+)",
        "devisesquare:square-buy",
    ),
    "ZWG": (
        "ZWE",
        "https://www.zimpricecheck.com/price-updates/official-and-black-market-exchange-rates/",
        r"informal-sector rate\s*ZiG\s*([\d.]+)",
        "zimpricecheck:informal-mean",
    ),
    "MVR": (
        "MDV",
        "https://adhadhu.com/",
        r'dollarNav\\",\{[^}]*\},\\"rate\\",([\d.]+)',
        "adhadhu:dollar-rate",
    ),
}
_P2P_URL = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
P2P_FIATS = {"MZN": "MOZ", "GNF": "GIN", "TND": "TUN", "TTD": "TTO"}
SOURCE_P2P = "p2p:binance-usdt-top10-median"


def _this_month() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC").tz_localize(None).to_period("M").to_timestamp()


def append_current(
    previous: pd.DataFrame, source: str, currency: str, iso3: str, rate: float
) -> pd.DataFrame:
    """Earlier months of ``source`` from the cache plus this month's ``rate``."""
    month = _this_month()
    kept = previous[previous["source"].eq(source) & previous["date"].ne(month)]
    row = pd.DataFrame(
        [
            {
                "date": month,
                "rate_usd_to_local": float(rate),
                "markets": 1,
                "currency": currency,
                "iso3": iso3,
                "source": source,
            }
        ]
    )
    return pd.concat([kept, row], ignore_index=True)


def mmk_series(session) -> pd.DataFrame | None:
    page = session.get(_CBM_PAGE, timeout=60)
    link = BeautifulSoup(page.text, "lxml").select_one("a[href$='.xlsx']")
    raw = session.get(urljoin(page.url, link["href"]), timeout=120).content
    df = pd.read_excel(io.BytesIO(raw), header=None, usecols=range(6), skiprows=3)
    df = df.assign(
        date=pd.to_datetime(df[0], errors="coerce"),
        rate=pd.to_numeric(df[4], errors="coerce"),
    ).dropna(subset=["date", "rate"])
    monthly = (
        df.assign(date=df["date"].dt.to_period("M").dt.to_timestamp())
        .groupby("date")
        .agg(rate_usd_to_local=("rate", "median"), markets=("rate", "size"))
    )
    return monthly.reset_index().assign(currency="MMK", iso3="MMR", source=SOURCE_MMK)


def portal_rate(session, currency: str) -> float:
    _, url, pattern, _ = _PORTALS[currency]
    html = session.get(url, timeout=60).text
    text = (
        html
        if currency == "MVR"
        else BeautifulSoup(html, "lxml").get_text(" ", strip=True)
    )
    hits = re.findall(pattern, text, re.I)
    if currency == "DZD":
        return float(f"{hits[0][0]}.{hits[0][1]}")
    return statistics.mean(float(h) for h in hits)


def p2p_rate(session, fiat: str) -> float:
    """Median of the top 10 BUY ads; SELL ads when a market has no BUY ads (TTD)."""
    for side in ("BUY", "SELL"):
        body = {
            "fiat": fiat,
            "asset": "USDT",
            "tradeType": side,
            "page": 1,
            "rows": 10,
            "payTypes": [],
            "publisherType": None,
        }
        ads = session.post(_P2P_URL, json=body, timeout=30).json().get("data") or []
        if ads:
            return statistics.median(float(a["adv"]["price"]) for a in ads)
    raise ValueError(f"no P2P ads for {fiat}")


def extra_series(session, previous: pd.DataFrame) -> list[pd.DataFrame]:
    out: list[pd.DataFrame] = []
    try:
        out.append(mmk_series(session))
    except Exception as exc:
        logger.warning("MMK parallel fetch failed: %s", exc)
    for currency, (iso3, _, _, source) in _PORTALS.items():
        series = previous[previous["source"].eq(source)]
        try:
            series = append_current(
                previous, source, currency, iso3, portal_rate(session, currency)
            )
        except Exception as exc:
            logger.warning("%s parallel fetch failed: %s", currency, exc)
        if not series.empty:
            out.append(series)
    for fiat, iso3 in P2P_FIATS.items():
        source = f"{SOURCE_P2P}:{fiat}"
        series = previous[previous["source"].eq(source)]
        try:
            series = append_current(
                previous, source, fiat, iso3, p2p_rate(session, fiat)
            )
        except Exception as exc:
            logger.warning("%s P2P fetch failed: %s", fiat, exc)
        if not series.empty:
            out.append(series)
    return out
