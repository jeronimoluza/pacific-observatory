"""LTA — Bus & MRT fare table (Singapore), snapshot per published revision.

Downloads the static ``fare-table.pdf`` from LTA's DAM and emits PriceObservation
rows for the Adult Card / Basic Services tariff across all 39 distance bands.
Cash fares, concession cards (Senior / Student / WTCS) and Express Services
are visible in the same PDF but deferred — Adult Card Basic Services is the
canonical urban-transit fare for PPP comparison (COICOP 07.3.2).

The PDF header carries the effective date ("Fares effective from <date>") —
that is the observation_date, not the HTTP Last-Modified header.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date, datetime

import pandas as pd
import pdfplumber

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_PDF_URL = "https://www.lta.gov.sg/content/dam/ltagov/img/map/bus/fare-table.pdf"
_COUNTRY = "Singapore"
_CURRENCY = "SGD"
_SOURCE_KEY = "sg_lta_fares"
_SOURCE_URL = (
    "https://www.lta.gov.sg/content/ltagov/en/getting_around/public_transport/"
    "buses/bus_fares.html"
)
_COICOP = "07.3.2"
_UNIT = "journey"
_IDENT = ["source_key", "observation_date", "item_name"]

_EFFECTIVE_RE = re.compile(r"Fares effective from (\d{1,2} \w+ \d{4})")
_ADULT_SECTION_RE = re.compile(
    r"Adult Card Fares.*?(?=Workfare Transport Concession Scheme Card Fares)",
    re.DOTALL,
)
_FLOAT_RE = re.compile(r"\d+\.\d+")
_BAND_START_RE = re.compile(r"\d+\.\d+|>")


def _parse_section(adult_section: str) -> tuple[list[str], list[float]]:
    """Return (band_labels, basic_services_fares) — both length 39."""
    lines = adult_section.splitlines()
    starts_line = next(ln for ln in lines if ln and ln[0].isdigit())
    ends_line = next(ln for ln in lines if ln.startswith("-"))
    basic_line = next(ln for ln in lines if ln.startswith("Basic Services"))

    starts = _BAND_START_RE.findall(starts_line)
    ends = _FLOAT_RE.findall(ends_line)
    fares = [float(x) for x in _FLOAT_RE.findall(basic_line)]

    if not (len(starts) == len(ends) == len(fares)):
        raise ValueError(
            f"band-row length mismatch: starts={len(starts)} ends={len(ends)} fares={len(fares)}"
        )

    labels = []
    for s, e in zip(starts, ends):
        if s == ">":
            labels.append(f">{e} km")
        else:
            labels.append(f"{s}-{e} km")
    return labels, fares


def fetch_sg_lta_fares(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_PDF_URL, timeout=60)
    resp.raise_for_status()

    with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
        text = pdf.pages[0].extract_text() or ""

    m = _EFFECTIVE_RE.search(text)
    if not m:
        raise LookupError("effective-date header not found in fare-table.pdf")
    obs_date = datetime.strptime(m.group(1), "%d %B %Y").date()
    if obs_date <= cutoff:
        logger.info(
            "[%s] effective %s ≤ cutoff %s — nothing new", _SOURCE_KEY, obs_date, cutoff
        )
        return None

    section_m = _ADULT_SECTION_RE.search(text)
    if not section_m:
        raise LookupError("Adult Card Fares section not found in fare-table.pdf")
    labels, fares = _parse_section(section_m.group(0))

    rows: list[dict] = []
    for band, fare in zip(labels, fares):
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP,
            "item_name": f"Adult card fare, basic services, {band}",
            "price_local": fare,
            "currency": _CURRENCY,
            "unit": _UNIT,
            "source_url": _SOURCE_URL,
            "notes": "Public Transport Council distance-based fare structure",
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows)
