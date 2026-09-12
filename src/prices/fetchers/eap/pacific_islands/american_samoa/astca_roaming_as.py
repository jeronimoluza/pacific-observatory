"""ASTCA American Samoa prepaid mobile roaming tariff."""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://www.astca.net/prepaid-mobile/roaming/"
_COUNTRY = "American Samoa"
_CURRENCY = "USD"
_SOURCE_KEY = "as_astca_roaming"
_IDENT = ["source_key", "observation_date", "item_name", "unit"]

_PRICE_RE = re.compile(r"\$\s*(?P<price>\d[\d,]*(?:\.\d+)?)")

# COICOP 2018: voice/SMS -> mobile telephone services; data -> internet access;
# mixed data+voice+SMS bundles -> bundled telecommunication services.
_COICOP_VOICE_SMS = "08.3.2.0"
_COICOP_DATA = "08.3.3.0"
_COICOP_BUNDLE = "08.3.4.0"

_UNIT_BY_SERVICE = {"voice": "minute", "sms": "message", "data": "megabyte"}


def _clean(value) -> str:
    return " ".join(str(value).replace("\xa0", " ").split())


def _price(value) -> float | None:
    match = _PRICE_RE.search(_clean(value))
    if match is None:
        return None
    return float(match.group("price").replace(",", ""))


def _row(item_name: str, price: float, unit: str, coicop: str, notes: str, ts: str):
    row = {
        "observation_date": date.today().isoformat(),
        "period_kind": "current_tariff",
        "country": _COUNTRY,
        "subnational_area": None,
        "source_key": _SOURCE_KEY,
        "coicop_code": coicop,
        "item_name": item_name[:500],
        "price_local": round(price, 2),
        "currency": _CURRENCY,
        "unit": unit,
        "source_url": _URL,
        "notes": notes,
        "scrape_ts": ts,
        "observation_hash": None,
    }
    row["observation_hash"] = make_hash(row, _IDENT)
    return row


def _parse_payg(df: pd.DataFrame, ts: str) -> list[dict]:
    rows: list[dict] = []
    price_col = df.columns[0]
    for _, item in df.iterrows():
        price = _price(item[price_col])
        service = _clean(item.get("Service", "")).lower()
        if price is None or service not in _UNIT_BY_SERVICE:
            continue
        destination = _clean(item.get("Destination", ""))
        direction = _clean(item.get("Direction", ""))
        coicop = _COICOP_DATA if service == "data" else _COICOP_VOICE_SMS
        label_parts = ["Prepaid roaming", service, "pay-as-you-go"]
        if destination and destination.lower() != "nan":
            label_parts.append(f"to/from {destination}")
        if direction and direction.lower() != "nan":
            label_parts.append(f"({direction})")
        rows.append(
            _row(
                " ".join(label_parts),
                price,
                _UNIT_BY_SERVICE[service],
                coicop,
                "ASTCA prepaid roaming pay-as-you-go rate",
                ts,
            )
        )
    return rows


def _parse_bundles(df: pd.DataFrame, ts: str) -> list[dict]:
    rows: list[dict] = []
    for _, item in df.iterrows():
        price = _price(item.get("Bundle Price", ""))
        if price is None:
            continue
        allotment = _clean(item.get("Allotments", ""))
        services = _clean(item.get("Service(s)", ""))
        validity = _clean(item.get("Validity Period", ""))
        coicop = _COICOP_BUNDLE
        lowered = services.lower()
        if lowered == "data":
            coicop = _COICOP_DATA
        elif "data" not in lowered:
            coicop = _COICOP_VOICE_SMS
        rows.append(
            _row(
                f"Prepaid roaming bundle {allotment} ({services}), {validity}",
                price,
                "bundle",
                coicop,
                f"ASTCA prepaid roaming bundle; validity={validity}",
                ts,
            )
        )
    return rows


def fetch_as_astca_roaming(cutoff: date) -> pd.DataFrame | None:
    today = date.today()
    if today <= cutoff:
        return None

    session = get_session()
    session.headers.update({"User-Agent": "Mozilla/5.0 price-research"})
    resp = session.get(_URL, timeout=60)
    resp.raise_for_status()

    tables = pd.read_html(io.StringIO(resp.text))
    ts = get_scrape_ts()
    rows: list[dict] = []
    for table in tables:
        columns = {_clean(c) for c in table.columns}
        if "Service" in columns and "Destination" in columns:
            rows.extend(_parse_payg(table, ts))
        elif "Bundle Price" in columns:
            rows.extend(_parse_bundles(table, ts))

    if not rows:
        logger.warning("[%s] no roaming rate rows parsed", _SOURCE_KEY)
        return None
    out = pd.DataFrame(rows).drop_duplicates(subset=["observation_hash"])
    logger.info("[%s] parsed %d roaming tariff rows", _SOURCE_KEY, len(out))
    return out
