"""American Samoa official taxi-rate regulation."""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://asbar.org/regulation/19-0170-taxi-rates/"
_COUNTRY = "American Samoa"
_CURRENCY = "USD"
_SOURCE_KEY = "as_asbar_taxi_rates"
_COICOP = "07.3.2"
_IDENT = ["source_key", "observation_date", "item_name", "unit"]

_RATE_RE = re.compile(r"^(?P<label>.+?)\s+\$?(?P<price>\d+(?:\.\d+)?)$")
_CHARTER_RE = re.compile(
    r"Charter:\s*\$(?P<charter>\d+(?:\.\d+)?)\s*per hour;\s*"
    r"waiting:\s*\$(?P<waiting>\d+(?:\.\d+)?)\s*for 15 minutes;\s*"
    r"minimum charge:\s*\$(?P<minimum>\d+(?:\.\d+)?)",
    re.I,
)
_EXCESS_LUGGAGE_RE = re.compile(
    r"\$(?P<price>\d+(?:\.\d+)?)\s+for each piece of excess luggage", re.I
)

_SECTIONS = {
    "Village/Area One Way Fare West From Market Place (Fagatogo)": (
        "from Fagatogo market, westbound"
    ),
    "Village/Area One Way Fare East From Market Place (Fagatogo)": (
        "from Fagatogo market, eastbound"
    ),
    "Village/Area One Way Fare West of Pago Pago International Airport": (
        "from Pago Pago International Airport, westbound"
    ),
    "Village/Area One Way Fare East of Pago Pago International Airport": (
        "from Pago Pago International Airport, eastbound"
    ),
}


def _clean(value: str) -> str:
    value = value.replace("\xa0", " ")
    value = re.sub(r"[.\u2026]{2,}", " ", value)
    return " ".join(value.split()).strip()


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


def _parse_route_rows(text: str, ts: str) -> list[dict]:
    rows: list[dict] = []
    section: str | None = None

    for raw_line in text.splitlines():
        line = _clean(raw_line)
        if not line:
            continue
        if line in _SECTIONS:
            section = _SECTIONS[line]
            continue
        if line.startswith("(b) Charter:"):
            break
        if section is None:
            continue
        match = _RATE_RE.match(line)
        if not match:
            continue
        label = _clean(match.group("label"))
        price = float(match.group("price"))
        rows.append(
            _row(
                f"Taxi one-way fare, {section}, {label}",
                price,
                "trip",
                f"Official maximum permissible taxi rate; route={section}",
                ts,
            )
        )

    return rows


def _parse_supplemental_rows(text: str, ts: str) -> list[dict]:
    rows: list[dict] = []
    charter = _CHARTER_RE.search(text)
    if charter:
        rows.extend(
            [
                _row(
                    "Taxi charter rate",
                    float(charter.group("charter")),
                    "hour",
                    "Official taxi charter rate",
                    ts,
                ),
                _row(
                    "Taxi waiting charge",
                    float(charter.group("waiting")),
                    "15_minutes",
                    "Official taxi waiting charge",
                    ts,
                ),
                _row(
                    "Taxi minimum charge",
                    float(charter.group("minimum")),
                    "trip",
                    "Official minimum taxi charge",
                    ts,
                ),
            ]
        )

    luggage = _EXCESS_LUGGAGE_RE.search(text)
    if luggage:
        rows.append(
            _row(
                "Taxi excess luggage charge",
                float(luggage.group("price")),
                "piece",
                "Official charge per piece above the free luggage allowance",
                ts,
            )
        )

    return rows


def fetch_as_asbar_taxi_rates(cutoff: date) -> pd.DataFrame | None:
    today = date.today()
    if today <= cutoff:
        return None

    session = get_session()
    session.headers.update({"User-Agent": "Mozilla/5.0 price-research"})
    resp = session.get(_URL, timeout=45)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    text = soup.get_text("\n", strip=True)
    ts = get_scrape_ts()
    rows = _parse_route_rows(text, ts) + _parse_supplemental_rows(text, ts)

    logger.info("[%s] parsed %d taxi-rate rows", _SOURCE_KEY, len(rows))
    return pd.DataFrame(rows) if rows else None
