"""American Samoa Port Administration water-transportation fares."""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://portadministration.as.gov/services/water-transportation-wtd"
_COUNTRY = "American Samoa"
_CURRENCY = "USD"
_SOURCE_KEY = "as_port_wtd_fares"
_COICOP = "07.3.3"
_IDENT = ["source_key", "observation_date", "item_name", "unit"]

_MONEY_RE = re.compile(r"\$(?P<price>\d+(?:\.\d+)?)")
_SECTION_NAMES = {
    "CARGO",
    "HAZARDOUS CARGO",
    "CONSTRUCTION MATERIAL",
    "VEHICLES",
    "SERVICE CHARGE",
}


def _clean(value: object) -> str:
    if pd.isna(value):
        return ""
    return " ".join(str(value).replace("\xa0", " ").split()).strip()


def _price(value: object) -> float | None:
    match = _MONEY_RE.search(_clean(value))
    return float(match.group("price")) if match else None


def _unit(text: str, default: str) -> str:
    lowered = text.lower()
    if "round" in lowered:
        return "round_trip"
    if "one-way" in lowered or "one way" in lowered:
        return "one_way"
    if "per gallon" in lowered:
        return "gallon"
    if "per drum" in lowered:
        return "drum"
    if "per cubic ft" in lowered:
        return "cubic_ft"
    if "per sheet" in lowered:
        return "sheet_6ft"
    if "per bag" in lowered:
        return "bag"
    if "per pallet" in lowered:
        return "pallet"
    if "per customer" in lowered:
        return "customer"
    return default


def _row(item_name: str, price: float, unit: str, notes: str, ts: str) -> dict:
    row = {
        "observation_date": date.today().isoformat(),
        "period_kind": "current_tariff",
        "country": _COUNTRY,
        "source_key": _SOURCE_KEY,
        "coicop_code": _COICOP,
        "item_name": item_name,
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


def _passenger_rows(table: pd.DataFrame, ts: str) -> list[dict]:
    rows: list[dict] = []
    header = [_clean(v) for v in table.iloc[0].tolist()]
    for _, rec in table.iloc[1:].iterrows():
        label = _clean(rec.iloc[0])
        if not label:
            continue
        for col_idx, fare_kind in enumerate(header[1:], start=1):
            price = _price(rec.iloc[col_idx])
            if price is None or price <= 0:
                continue
            fare_label = fare_kind.lower().replace("round- trip", "round-trip")
            rows.append(
                _row(
                    f"Manuatele ferry passenger fare, {label}, {fare_label}",
                    price,
                    _unit(fare_kind, "fare"),
                    "Official Port Administration inter-island passenger ferry fare",
                    ts,
                )
            )
    return rows


def _other_fare_rows(table: pd.DataFrame, ts: str) -> list[dict]:
    rows: list[dict] = []
    section = ""
    last_item = ""

    for _, rec in table.iterrows():
        cells = [_clean(v) for v in rec.tolist()]
        if not any(cells):
            continue
        nonempty = [c for c in cells if c]
        if len(set(nonempty)) == 1 and nonempty[0] in _SECTION_NAMES:
            section = nonempty[0].title()
            last_item = ""
            continue

        first, second, third = cells
        text = " ".join(c for c in cells if c)
        price = _price(third) or _price(second) or _price(first)
        if price is None or price <= 0:
            continue

        if section == "Service Charge":
            label = first.split("-", 1)[0].strip()
            item_name = f"Port water-transportation service charge, {label}"
        else:
            item = first or last_item
            detail = second if second and _price(second) is None else ""
            item_name = f"Port water-transportation {section.lower()} fare, {item}"
            if detail:
                item_name = f"{item_name}, {detail}"
            last_item = item

        rows.append(
            _row(
                item_name,
                price,
                _unit(text, "fare"),
                f"Official Port Administration table section={section}",
                ts,
            )
        )

    return rows


def fetch_as_port_wtd_fares(cutoff: date) -> pd.DataFrame | None:
    today = date.today()
    if today <= cutoff:
        return None

    session = get_session()
    session.headers.update({"User-Agent": "Mozilla/5.0 price-research"})
    resp = session.get(_URL, timeout=45)
    resp.raise_for_status()

    tables = pd.read_html(io.StringIO(resp.text))
    if len(tables) < 2:
        logger.warning("[%s] expected at least two fare tables", _SOURCE_KEY)
        return None

    ts = get_scrape_ts()
    rows = _passenger_rows(tables[0], ts) + _other_fare_rows(tables[1], ts)

    logger.info("[%s] parsed %d water-transportation fare rows", _SOURCE_KEY, len(rows))
    return pd.DataFrame(rows) if rows else None
