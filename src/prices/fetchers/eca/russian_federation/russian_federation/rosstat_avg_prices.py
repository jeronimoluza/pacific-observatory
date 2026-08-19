"""Rosstat average consumer prices — monthly item-level averages, national level.

rosstat.gov.ru/statistics/price links a cumulative-year XLSX
("sred_potreb_cen_MM-YYYY.xlsx") of "Средние потребительские цены (тарифы)
на товары и услуги" — Rosstat's own item-level average consumer price survey,
one sheet per month, ~560 named goods/services x federal/district/oblast/city
territory rows. This fetcher takes the Russian Federation (territory code 643)
row only, i.e. national-level averages; the same workbook also carries
federal-district, oblast, and surveyed-city breakdowns that a future pass
could extract.

rosstat.gov.ru presents a valid *.rosstat.gov.ru leaf certificate chained to
a Russian government CA ("Russian Trusted Root/Sub CA") that is not in any
standard trust store, and the server does not send the intermediate cert in
the handshake -- verification fails with "unable to get local issuer
certificate" even though the chain itself is valid. The fix is to vendor the
missing sub+root CA certs (fetched from the leaf cert's own Authority
Information Access URL and the official gosuslugi.ru CA bundle) and pass them
as `verify=`, not to skip verification.
"""

from __future__ import annotations

import io
import logging
import re
import tempfile
from datetime import date
from functools import lru_cache
from pathlib import Path

import certifi
import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_CHAIN_PEM = Path(__file__).with_name("_rosstat_gov_ru_chain.pem")


@lru_cache(maxsize=1)
def _ca_bundle() -> str:
    bundle = Path(tempfile.gettempdir()) / "rosstat_gov_ru_ca_bundle.pem"
    bundle.write_bytes(
        Path(certifi.where()).read_bytes() + b"\n" + _CHAIN_PEM.read_bytes()
    )
    return str(bundle)


_INDEX_URL = "https://rosstat.gov.ru/statistics/price"
_COUNTRY = "Russian Federation"
_CURRENCY = "RUB"
_SOURCE_KEY = "ru_rosstat_avg_prices"
_IDENT = ["source_key", "observation_date", "item_name", "unit"]
_XLSX_RE = re.compile(
    r'href="(/storage/mediabank/sred_potreb_cen_(\d{2})-(\d{4})\.xlsx)"'
)
_SHEET_RE = re.compile(r"^(\d{2})\((\d{4})\)$")
_RF_TERRITORY_CODE = 643


def _find_latest_xlsx_url(html: str) -> str | None:
    matches = _XLSX_RE.findall(html)
    if not matches:
        return None
    best = max(matches, key=lambda m: (int(m[2]), int(m[1])))
    return "https://rosstat.gov.ru" + best[0]


def _parse_sheet(
    df: pd.DataFrame, sheet_name: str, xlsx_url: str, cutoff: date
) -> list[dict]:
    m = _SHEET_RE.match(sheet_name)
    if not m:
        return []
    month, year = int(m.group(1)), int(m.group(2))
    obs_date = date(year, month, 1)
    if obs_date <= cutoff:
        return []

    rf_rows = df[df.iloc[:, 0] == _RF_TERRITORY_CODE]
    if rf_rows.empty:
        logger.warning("[%s] no RF-level row in sheet %s", _SOURCE_KEY, sheet_name)
        return []
    names = df.iloc[4, 2:]
    values = rf_rows.iloc[0, 2:]

    ts = get_scrape_ts()
    rows: list[dict] = []
    for name, value in zip(names, values):
        if not isinstance(name, str) or not name.strip():
            continue
        try:
            price = float(value)
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue
        label = name.strip()
        if "," in label:
            item_name, unit = (p.strip() for p in label.rsplit(",", 1))
        else:
            item_name, unit = label, "each"
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "monthly_avg",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": item_name,
            "price_local": round(price, 2),
            "currency": _CURRENCY,
            "unit": unit,
            "source_url": xlsx_url,
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)
    return rows


def fetch_ru_rosstat_avg_prices(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    try:
        page = session.get(_INDEX_URL, timeout=30, verify=_ca_bundle())
        page.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] index page fetch failed: %s", _SOURCE_KEY, exc)
        return None

    xlsx_url = _find_latest_xlsx_url(page.text)
    if not xlsx_url:
        logger.warning(
            "[%s] no sred_potreb_cen_*.xlsx link found on index page", _SOURCE_KEY
        )
        return None

    try:
        resp = session.get(xlsx_url, timeout=90, verify=_ca_bundle())
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] xlsx fetch failed: %s", _SOURCE_KEY, exc)
        return None

    try:
        xl = pd.ExcelFile(io.BytesIO(resp.content))
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] xlsx parse failed: %s", _SOURCE_KEY, exc)
        return None

    rows: list[dict] = []
    for sheet_name in xl.sheet_names:
        if sheet_name == "Содержание":
            continue
        df = xl.parse(sheet_name, header=None)
        rows.extend(_parse_sheet(df, sheet_name, xlsx_url, cutoff))

    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
