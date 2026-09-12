"""Eswatini Electricity Company (EEC) -- residential/domestic electricity
tariff schedule, https://www.eec.co.sz/domestic/tariffs/.

Plain server-rendered Bootstrap page (no WAF, no JS): the whole schedule is
one `<table>` inside `<section id="MainText">`, headed by a `.section-title`
`<h2>` carrying the tariff year ("2026/2027 -- Residential/Domestic
Tariffs"). Columns are Type | Non-TOU Tariffs | Facility Charge E/Month |
Energy Charge E/kWh.

Scope: the DOMESTIC schedule only. EEC publishes separate commercial pages
(/commercial/tariffs/, plus four time-of-use schedules T1-T4) which are
business tariffs, not household final consumption, and are deliberately
not walked here.

Two price components are emitted per row when both are printed:
  * the per-kWh energy charge (unit "kWh") -- present on every row;
  * the fixed monthly facility charge (unit "month") -- printed only for
    S2 General Purpose on the schedule as of onboarding, blank for S10/S1.
Emitting both rather than dropping the fixed charge (the choice made by
epal_water_tariff_ao) because here the two are cleanly separable per row
and a household on S2 genuinely pays both.

The page states the energy charge is "inclusive of 2.5% levy (of the
energy charge) for Rural Electrification Access Fund and exclusive of the
Value Added Tax (VAT) applicable to all non-domestic customers" -- i.e.
domestic rows are already the consumer-facing price. Recorded per row in
`notes`.

No commencement date is printed anywhere on the page -- only the
"2026/2027" tariff-year label -- so `period_kind` is "snapshot" (scrape
date) and the tariff-year label is carried in `notes`. Same reasoning as
epal_water_tariff_ao.py: this is "whatever EEC currently publishes as
live", not a dated tariff order with a parseable effective_from.

Currency SZL (Lilangeni), matching countries.yaml's Eswatini default; the
table's own column headers denominate in "E" (Emalangeni).
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://www.eec.co.sz/domestic/tariffs/"
_COUNTRY = "Eswatini"
_CURRENCY = "SZL"
_SOURCE_KEY = "eec_domestic_tariffs_sz"
_COICOP_CODE = "04.5.1.0"
_IDENT = ["source_key", "observation_date", "item_name"]

_NUM_RE = re.compile(r"^\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*$")
_YEAR_RE = re.compile(r"(\d{4}\s*/\s*\d{2,4})")


def _parse_amount(text: str) -> float | None:
    """Parse an Emalangeni amount cell. Blank cells (and the page's
    &nbsp; placeholders) return None rather than 0."""
    cleaned = (text or "").replace("\xa0", " ").strip()
    if not cleaned:
        return None
    m = _NUM_RE.match(cleaned)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def _parse_page(html_text: str) -> tuple[str | None, list[dict]]:
    soup = BeautifulSoup(html_text, "html.parser")
    main = soup.find("section", id="MainText")
    if main is None:
        return None, []

    title = main.find(class_="section-title")
    year_label = None
    if title is not None:
        m = _YEAR_RE.search(title.get_text(" ", strip=True))
        if m:
            year_label = re.sub(r"\s+", "", m.group(1))

    table = main.find("table")
    if table is None:
        return year_label, []

    rows: list[dict] = []
    for tr in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all("td")]
        if len(cells) < 4:
            continue
        code, label, facility, energy = cells[:4]
        code = code.replace("\xa0", " ").strip()
        label = label.replace("\xa0", " ").strip()
        if not code:
            continue
        name = f"{code} {label}".strip()

        energy_price = _parse_amount(energy)
        if energy_price is not None:
            rows.append(
                {
                    "item_name": f"Electricity energy charge -- {name}",
                    "price_local": energy_price,
                    "unit": "kWh",
                }
            )
        facility_price = _parse_amount(facility)
        if facility_price is not None:
            rows.append(
                {
                    "item_name": f"Electricity facility charge -- {name}",
                    "price_local": facility_price,
                    "unit": "month",
                }
            )
    return year_label, rows


def fetch_eec_domestic_tariffs_sz(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_URL, timeout=30)
    if resp.status_code != 200:
        logger.warning("[%s] HTTP %d for %s", _SOURCE_KEY, resp.status_code, _URL)
        return None

    year_label, parsed = _parse_page(resp.text)
    if not parsed:
        logger.warning(
            "[%s] No tariff rows parsed from %s -- page layout may have changed",
            _SOURCE_KEY,
            _URL,
        )
        return None

    obs_date = date.today()
    if obs_date <= cutoff:
        return None

    note = "Domestic (non-TOU) schedule"
    if year_label:
        note = f"{note}; tariff year {year_label}"
    note = (
        f"{note}; energy charge includes the 2.5% Rural Electrification "
        f"Access Fund levy and excludes VAT (VAT applies to non-domestic "
        f"customers only, per EEC)"
    )

    ts = get_scrape_ts()
    rows = []
    for item in parsed:
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "subnational_area": None,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP_CODE,
            "item_name": item["item_name"],
            "price_local": item["price_local"],
            "currency": _CURRENCY,
            "unit": item["unit"],
            "source_url": _URL,
            "notes": note,
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows) if rows else None
