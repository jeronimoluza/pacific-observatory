"""OMH Madagascar — Office Malgache des Hydrocarbures retail prices.

`https://www.omh.mg/index.php?page=prixevomensuel` lists the last 3-4
months of pump prices, and `?page=prixevoannuel` lists annual averages
back to 2015. Both tables share the same `Année | SC | PL | GO` schema
(Ariary/litre) where SC = Super Carburant (gasoline), PL = Pétrole
Lampant (kerosene), GO = Gasoil (diesel). Annual rows are emitted with
observation_date = Jan 1 of that year, and only for years strictly
before the earliest monthly row to avoid mixing cadences. The site has
an invalid TLS cert chain so HTTPS runs with verification disabled.
"""

import logging
import warnings
from datetime import date

import pandas as pd
import requests
import urllib3
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_MONTHLY_URL = "https://www.omh.mg/index.php?page=prixevomensuel"
_ANNUAL_URL = "https://www.omh.mg/index.php?page=prixevoannuel"
_COUNTRY = "Madagascar"
_CURRENCY = "MGA"
_SOURCE_KEY = "omh_mg_monthly"

# Raw column code → canonical product name.
_PRODUCTS = {
    "SC": "Super Carburant",  # gasoline 95
    "PL": "Pétrole Lampant",  # kerosene
    "GO": "Gasoil",  # diesel
}

# French month → number. Both accented and unaccented variants accepted.
_FR_MONTHS = {
    "janvier": 1,
    "février": 2,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "août": 8,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "décembre": 12,
    "decembre": 12,
}


def _parse_month_year(text: str) -> date | None:
    parts = text.strip().split()
    if len(parts) < 2:
        return None
    month = _FR_MONTHS.get(parts[0].lower())
    if month is None:
        return None
    try:
        year = int(parts[-1])
    except ValueError:
        return None
    try:
        return date(year, month, 1)
    except ValueError:
        return None


def _parse_price(text: str) -> float | None:
    cleaned = text.replace("\xa0", "").replace(" ", "").replace(",", ".").strip()
    if not cleaned:
        return None
    try:
        val = float(cleaned)
    except ValueError:
        return None
    return val if val > 0 else None


def _fetch_html(url: str) -> str:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", urllib3.exceptions.InsecureRequestWarning)
        resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=30,
            verify=False,
        )
    resp.raise_for_status()
    return resp.text


def _find_price_table(html: str) -> "list[list[str]]":
    soup = BeautifulSoup(html, "lxml")
    for table in soup.find_all("table"):
        trs = table.find_all("tr")
        if not trs:
            continue
        header_cells = [c.get_text(strip=True) for c in trs[0].find_all(["th", "td"])]
        if header_cells[:4] == ["Année", "SC", "PL", "GO"]:
            return [
                [c.get_text(strip=True) for c in tr.find_all(["th", "td"])]
                for tr in trs[1:]
            ]
    return []


def _row_to_records(obs_date: date, cells: "list[str]") -> "list[dict]":
    iso = obs_date.strftime("%Y-%m-%d")
    out = []
    for col_idx, code in enumerate(("SC", "PL", "GO"), start=1):
        if col_idx >= len(cells):
            continue
        price = _parse_price(cells[col_idx])
        if price is None:
            continue
        out.append(
            {
                "observation_date": iso,
                "country": _COUNTRY,
                "fuel_product": _PRODUCTS[code],
                "price_local": price,
                "currency": _CURRENCY,
                "unit": "L",
                "source_key": _SOURCE_KEY,
            }
        )
    return out


def fetch_omh_mg(cutoff: date) -> pd.DataFrame | None:
    rows_out: list[dict] = []
    earliest_monthly: date | None = None

    monthly_rows = _find_price_table(_fetch_html(_MONTHLY_URL))
    if not monthly_rows:
        logger.warning(
            "[omh_mg] monthly retail-price table not found at %s", _MONTHLY_URL
        )
    for cells in monthly_rows:
        if len(cells) < 4:
            continue
        obs_date = _parse_month_year(cells[0])
        if obs_date is None:
            continue
        if earliest_monthly is None or obs_date < earliest_monthly:
            earliest_monthly = obs_date
        if obs_date <= cutoff:
            continue
        rows_out.extend(_row_to_records(obs_date, cells))

    try:
        annual_rows = _find_price_table(_fetch_html(_ANNUAL_URL))
    except Exception:
        logger.exception("[omh_mg] annual page fetch failed; skipping backfill")
        annual_rows = []
    for cells in annual_rows:
        if len(cells) < 4:
            continue
        try:
            year = int(cells[0].strip())
        except ValueError:
            continue
        obs_date = date(year, 1, 1)
        # Skip the current/recent years already represented by monthly rows.
        if earliest_monthly is not None and obs_date >= date(
            earliest_monthly.year, 1, 1
        ):
            continue
        # Annual backfill rows are stable history — emit them unconditionally
        # and let the loader's hash-based dedup handle prior runs.
        rows_out.extend(_row_to_records(obs_date, cells))

    if not rows_out:
        logger.info("[omh_mg] No rows after cutoff %s", cutoff)
        return None

    df = (
        pd.DataFrame(rows_out)
        .drop_duplicates(subset=["observation_date", "fuel_product"])
        .sort_values(["observation_date", "fuel_product"])
        .reset_index(drop=True)
    )
    logger.info(
        "[omh_mg] %d rows (%s → %s)",
        len(df),
        df["observation_date"].iloc[0],
        df["observation_date"].iloc[-1],
    )
    return df


__all__ = ["fetch_omh_mg"]
