"""Ministry of Energy (mev.gov.ua) — Ukraine household electricity tariff.

The regulated residential electricity tariff is published as a server-rendered
HTML table on the Ministry of Energy "tariffs and prices" page: a two-column
``Time | Tariff`` table giving the time-of-use household rates (e.g. day
4.32 UAH/kWh, night 2.16 UAH/kWh). This is an administered price, so a snapshot
is recorded each run and accumulated by observation_hash (idempotent within a
day; a new row only when the regulated rate changes).

analytical_role: tariff · coicop_classification: source_curated
Household electricity maps to COICOP 04.5.1 (electricity).
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

from prices.fetchers.utils import get_scrape_ts, make_hash

logger = logging.getLogger(__name__)

_URL = "https://www.mev.gov.ua/en/storinka/tariffs-and-prices"
_COUNTRY = "Ukraine"
_CURRENCY = "UAH"
_SOURCE_KEY = "ua_mev_electricity"
_COICOP = "04.5.1"  # Electricity

# "4.32 UAH/kWh" / "2,16 UAH/kWh" -> float
_RATE_RE = re.compile(r"(\d+[.,]\d+)\s*UAH\s*/\s*kWh", re.IGNORECASE)
_TIME_RE = re.compile(r"\d{1,2}:\d{2}")

_IDENT = ["source_key", "observation_date", "item_name"]


def _parse_rate(text: str) -> float | None:
    m = _RATE_RE.search(text)
    if not m:
        return None
    return float(m.group(1).replace(",", "."))


def fetch_ua_mev_electricity(cutoff: date) -> pd.DataFrame | None:
    # mev.gov.ua sits behind a WAF that blocks the plain-requests TLS
    # fingerprint (403), so impersonate a real Chrome via curl_cffi.
    resp = cffi_requests.get(_URL, timeout=30, impersonate="chrome")
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    obs_date = date.today().isoformat()
    rows: list[dict] = []
    seen: set[str] = set()

    for table in soup.find_all("table"):
        header = table.find("tr")
        head_txt = header.get_text(" ", strip=True).lower() if header else ""
        # Only the household "Time | Tariff" table carries direct UAH/kWh rates;
        # the coefficient table expresses rates parenthetically and is skipped.
        if "tariff" not in head_txt:
            continue
        for tr in table.find_all("tr")[1:]:
            tds = tr.find_all(["td", "th"])
            if len(tds) < 2:
                continue
            time_label = tds[0].get_text(" ", strip=True)
            if not _TIME_RE.search(time_label):
                continue
            rate = _parse_rate(tds[1].get_text(" ", strip=True))
            if rate is None or not 0.1 < rate < 100:
                continue
            item_name = f"Household electricity ({time_label})"
            if item_name in seen:
                continue
            seen.add(item_name)
            row = {
                "observation_date": obs_date,
                "period_kind": "snapshot",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": _COICOP,
                "item_name": item_name,
                "price_local": rate,
                "currency": _CURRENCY,
                "unit": "kWh",
                "source_url": _URL,
                "notes": "Regulated residential time-of-use tariff",
                "scrape_ts": get_scrape_ts(),
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    if not rows:
        logger.warning("mev_electricity: no household tariff rows parsed")
        return None
    return pd.DataFrame(rows)
