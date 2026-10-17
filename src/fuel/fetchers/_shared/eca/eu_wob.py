"""European Commission Weekly Oil Bulletin (WOB) — consumer prices with taxes.

Replaces autotraveler.ru for the 27 EU members (autotraveler stopped updating).

Sources (https://energy.ec.europa.eu/data-and-analysis/weekly-oil-bulletin_en):
  1. History XLSX (stable link, refreshed weekly), sheet "Prices with taxes":
     row 0 = column keys like ``PL_price_with_tax_euro95`` / ``PL_exchange_rate``,
     rows 3.. = one Monday per row, newest first, 2005 onwards.
  2. Latest weekly XLSX "Weekly prices with Taxes" (link changes every week;
     discovered on the landing page). Used only for a week the history file
     does not have yet.

All prices are EUR per 1000 L. ``XX_exchange_rate`` is EUR per unit of
national currency; the national price is EUR price / rate. Prices without
taxes are a different sheet and are never read here (not retail).
"""

import functools
import io
import logging
import re
from datetime import date

import pandas as pd
from core.http import make_session

logger = logging.getLogger(__name__)

_BASE = "https://energy.ec.europa.eu"
_PAGE_URL = f"{_BASE}/data-and-analysis/weekly-oil-bulletin_en"
_HISTORY_URL = (
    f"{_BASE}/document/download/906e60ca-8b6a-44e7-8589-652854d2fd3f_en"
    "?filename=Weekly_Oil_Bulletin_Prices_History_maticni_4web.xlsx"
)
_LATEST_RE = re.compile(
    r'href="(/document/download/[^"]+Weekly%20prices%20with%20Taxes[^"]*)"'
)

# WOB column suffix → raw product label (the YAML products keys).
_PRODUCTS = {
    "euro95": "Euro-super 95",
    "diesel": "Automotive gas oil",
    "heating_oil": "Heating gas oil",
    "LPG": "LPG motor fuel",
}
# Latest-file column index (Sheet1, after the country name) per product.
_LATEST_COL = {"euro95": 1, "diesel": 2, "heating_oil": 3, "LPG": 6}

# WOB code → (country name in the latest file, national currency).
_COUNTRIES: dict[str, tuple[str, str]] = {
    "AT": ("Austria", "EUR"),
    "BE": ("Belgium", "EUR"),
    "BG": ("Bulgaria", "EUR"),
    "CY": ("Cyprus", "EUR"),
    "CZ": ("Czechia", "CZK"),
    "DE": ("Germany", "EUR"),
    "DK": ("Denmark", "DKK"),
    "EE": ("Estonia", "EUR"),
    "ES": ("Spain", "EUR"),
    "FI": ("Finland", "EUR"),
    "FR": ("France", "EUR"),
    "GR": ("Greece", "EUR"),
    "HR": ("Croatia", "EUR"),
    "HU": ("Hungary", "HUF"),
    "IE": ("Ireland", "EUR"),
    "IT": ("Italy", "EUR"),
    "LT": ("Lithuania", "EUR"),
    "LU": ("Luxembourg", "EUR"),
    "LV": ("Latvia", "EUR"),
    "MT": ("Malta", "EUR"),
    "NL": ("Netherlands", "EUR"),
    "PL": ("Poland", "PLN"),
    "PT": ("Portugal", "EUR"),
    "RO": ("Romania", "RON"),
    "SE": ("Sweden", "SEK"),
    "SI": ("Slovenia", "EUR"),
    "SK": ("Slovakia", "EUR"),
}


@functools.lru_cache(maxsize=1)
def _history() -> pd.DataFrame:
    resp = make_session().get(_HISTORY_URL, timeout=120)
    resp.raise_for_status()
    raw = pd.read_excel(
        io.BytesIO(resp.content), sheet_name="Prices with taxes", header=None
    )
    df = raw.iloc[3:].copy()
    df.columns = [str(c) for c in raw.iloc[0]]
    df = df.loc[:, ~df.columns.duplicated()]
    df["date"] = pd.to_datetime(
        df["Consumer prices of petroleum products inclusive of duties and taxes"],
        errors="coerce",
    )
    return df[df["date"].notna()].reset_index(drop=True)


@functools.lru_cache(maxsize=1)
def _latest() -> tuple[pd.Timestamp | None, dict[str, list]]:
    session = make_session()
    page = session.get(_PAGE_URL, timeout=60)
    page.raise_for_status()
    m = _LATEST_RE.search(page.text)
    if not m:
        logger.warning("[eu_wob] latest weekly link not found on %s", _PAGE_URL)
        return None, {}
    resp = session.get(_BASE + m.group(1).replace("&amp;", "&"), timeout=60)
    resp.raise_for_status()
    raw = pd.read_excel(io.BytesIO(resp.content), header=None)
    when = pd.to_datetime(raw.iloc[1, 0], errors="coerce")
    rows = {str(r[0]).strip(): list(r) for r in raw.iloc[2:].itertuples(index=False)}
    return (None if pd.isna(when) else when), rows


def _row(day, cc: str, product: str, price_eur, rate, currency: str, source_key: str):
    try:
        price_eur = float(price_eur)
    except (TypeError, ValueError):
        return None
    if not price_eur > 0:
        return None
    if currency != "EUR":
        try:
            rate = float(rate)
        except (TypeError, ValueError):
            return None
        if not rate > 0 or rate == 1:
            return None
        price = price_eur / rate
    else:
        price = price_eur
    return {
        "observation_date": day.strftime("%Y-%m-%d"),
        "country": _COUNTRIES[cc][0],
        "fuel_product": _PRODUCTS[product],
        "price_local": round(price, 4),
        "currency": currency,
        "unit": "1000 L",
        "source_key": source_key,
    }


def _fetch(cc: str, cutoff: date) -> pd.DataFrame | None:
    name, currency = _COUNTRIES[cc]
    source_key = f"eu_wob_{cc.lower()}_weekly"
    hist = _history()
    rate_col = f"{cc}_exchange_rate"
    rows = []
    for rec in hist[hist["date"].dt.date > cutoff].to_dict("records"):
        for product in _PRODUCTS:
            r = _row(
                rec["date"],
                cc,
                product,
                rec.get(f"{cc}_price_with_tax_{product}"),
                rec.get(rate_col),
                currency,
                source_key,
            )
            if r:
                rows.append(r)

    when, latest = _latest()
    if (
        when is not None
        and when > hist["date"].max()
        and when.date() > cutoff
        and name in latest
    ):
        rate = (
            hist.dropna(subset=[rate_col])[rate_col].iloc[0] if rate_col in hist else 1
        )
        for product, col in _LATEST_COL.items():
            r = _row(when, cc, product, latest[name][col], rate, currency, source_key)
            if r:
                rows.append(r)

    if not rows:
        logger.info("[eu_wob_%s] no rows after %s", cc.lower(), cutoff)
        return None
    df = pd.DataFrame(rows).sort_values(["observation_date", "fuel_product"])
    logger.info(
        "[eu_wob_%s] %d rows (%s → %s)",
        cc.lower(),
        len(df),
        df["observation_date"].iloc[0],
        df["observation_date"].iloc[-1],
    )
    return df.reset_index(drop=True)


def _make_fetcher(cc: str):
    def fetch(cutoff: date) -> pd.DataFrame | None:
        return _fetch(cc, cutoff)

    fetch.__name__ = f"fetch_eu_wob_{cc.lower()}"
    fetch.__doc__ = f"Weekly Oil Bulletin consumer prices for {_COUNTRIES[cc][0]}."
    return fetch


for _cc in _COUNTRIES:
    globals()[f"fetch_eu_wob_{_cc.lower()}"] = _make_fetcher(_cc)
