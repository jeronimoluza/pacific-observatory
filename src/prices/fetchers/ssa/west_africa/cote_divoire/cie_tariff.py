"""CIE (Compagnie Ivoirienne d'Electricité) — household electricity tariff, Côte d'Ivoire.

Scrapes the server-rendered "basse tension" (low voltage / residential) tariff
page at cie.ci. The page lists 8 tariff categories (Social, Général mono/tri,
Professionnel, Conventionnel, Eclairage Public), each with an accordion
`<h3>` header followed by a `<table>` of line items: "Prime fixe par
bimestre" and one or two kWh-block prices. The TTC (tax-included, last)
column is the consumer-facing FCFA price.

No effective/decision date is printed on the page — this is a live snapshot
of the tariff currently in force, so observation_date is the scrape date
(period_kind=snapshot), matching the our_telekom_plans.py convention.

NOTE: cie.ci serves only the leaf TLS certificate with no intermediate
(verified via `openssl s_client -showcerts`: 1 certificate in the chain, a
DigiCert Global G2 TLS RSA SHA256 2020 CA1 leaf with no CA1 intermediate
sent). This is a server misconfiguration, not a transient issue — every TLS
client (curl_cffi impersonate=chrome124 and plain requests) fails cert
verification identically. verify=False is required; the page carries no
credentials or user input, only published tariff data.

COICOP: 04.5.1 (electricity).
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_TARIFF_URL = "https://www.cie.ci/particuliers/tarifs-electricite"
_COUNTRY = "Cote d'Ivoire"
_CURRENCY = "XOF"
_SOURCE_KEY = "civ_cie_tariff"
_COICOP_CODE = "04.5.1"
_IDENT = ["source_key", "observation_date", "item_name"]

_PRICE_RE = re.compile(r"[\d\s ]+(?:,\d+)?")


def _parse_fcfa(text: str) -> float | None:
    """'31,72' -> 31.72 ; '1 240,00' -> 1240.00."""
    cleaned = text.strip().replace(" ", "").replace(" ", "")
    if not cleaned:
        return None
    cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _extract_tariff_rows(soup: BeautifulSoup, obs_date: date) -> list[dict]:
    rows: list[dict] = []
    headers = soup.find_all("h3", class_=re.compile(r"text-cie-blue"))
    for h3 in headers:
        category = h3.get_text(" ", strip=True)
        # Strip the leading "N - " ordinal prefix.
        category = re.sub(r"^\d+\s*-\s*", "", category)
        table = h3.find_parent("div").find_next("table")
        if table is None:
            continue
        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) < 4:
                continue
            designation = cells[0].get_text(" ", strip=True)
            ttc_text = cells[3].get_text(" ", strip=True)
            price_local = _parse_fcfa(ttc_text)
            if not designation or price_local is None:
                continue
            item_name = f"CIE {category}, {designation}"
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "snapshot",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": _COICOP_CODE,
                "item_name": item_name,
                "price_local": price_local,
                "currency": _CURRENCY,
                "unit": "kWh" if "kWh" in designation else "bimestre",
                "source_url": _TARIFF_URL,
                "notes": "FCFA (TTC) column, low-voltage (basse tension) household tariff schedule",
                "scrape_ts": get_scrape_ts(),
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)
    return rows


def fetch_civ_cie_tariff(cutoff: date) -> pd.DataFrame | None:
    obs_date = date.today()
    if obs_date <= cutoff:
        return None

    session = get_session()
    resp = session.get(_TARIFF_URL, timeout=30, verify=False)
    if resp.status_code != 200:
        logger.warning(
            "[%s] HTTP %d for %s", _SOURCE_KEY, resp.status_code, _TARIFF_URL
        )
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    rows = _extract_tariff_rows(soup, obs_date)
    if not rows:
        logger.warning("[%s] No tariff rows parsed from %s", _SOURCE_KEY, _TARIFF_URL)
        return None

    return pd.DataFrame(rows)
