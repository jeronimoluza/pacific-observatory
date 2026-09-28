"""Djibouti Telecom -- fixed-line (landline) prepaid tariff, from the public
"/internet/" plan page (Elementor price-table widgets, plain server-rendered
HTML, no WooCommerce/platform API behind it -- confirmed via /wp-json/ route
listing on 2026-09-28: only core WP plugin routes, no commerce endpoint).

Verified live 2026-09-28: GET https://www.djiboutitelecom.dj/internet/ ->
HTTP 200, 5 `.elementor-price-table` widgets with real DJF prices --
3 one-time installation-fee tiers ("Frais d'installation d'une ligne
telephonique": Djibouti-ville et Balbala / Etudiants / Regions) and 2
recurring prepaid-package tiers ("Mon forfait fixe prepaye": Djibouti-ville /
Regions). The /mobile/ and /pro/ pages on the same site carry no
`.elementor-price-table` widgets and no DJF/FDJ price text at all (checked
directly), so mobile and business plans are not covered by this fetcher.

Small, thin table (5 line items) but a genuine regulator/incumbent-set
administered tariff, not a retail catalog -- typical for this class of
source (cf. American Samoa astca_prepaid_as).

COICOP: entire page is landline telephone service -> 08.3.1.
"""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://www.djiboutitelecom.dj/internet/"
_COUNTRY = "Djibouti"
_CURRENCY = "DJF"
_SOURCE_KEY = "djtelecom_fixed_dji"
_COICOP = "08.3.1"  # Telephone/telefax equipment and services -- landline

_IDENT = ["source_key", "observation_date", "item_name"]


def fetch_djtelecom_fixed_dji(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    today = date.today()
    if today <= cutoff:
        return None

    ts = get_scrape_ts()
    rows: list[dict] = []
    for table in soup.select(".elementor-price-table"):
        heading = table.select_one(".elementor-price-table__heading")
        price_el = table.select_one(".elementor-price-table__price")
        if heading is None or price_el is None:
            continue
        price_text = price_el.get_text(" ", strip=True)
        digits = "".join(c for c in price_text if c.isdigit())
        if not digits:
            continue
        # The heading alone is ambiguous -- "RÉGIONS" is reused verbatim under
        # both the installation-fee section and the prepaid-package section
        # with two different prices. Disambiguate with the preceding <h2>
        # section title (confirmed live 2026-09-28: every price table sits
        # under exactly one h2).
        section = table.find_previous("h2")
        section_label = section.get_text(strip=True) if section else ""
        row = {
            "observation_date": today.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": (
                f"Djibouti Telecom fixe prepaye - {section_label} - "
                f"{heading.get_text(strip=True)}"
            ),
            "price_local": float(digits),
            "currency": _CURRENCY,
            "unit": "each",
            "coicop_code": _COICOP,
            "source_url": _URL,
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    if not rows:
        logger.warning("[%s] no price tables parsed from %s", _SOURCE_KEY, _URL)
        return None

    logger.info("[%s] %d rows from %s", _SOURCE_KEY, len(rows), _URL)
    return pd.DataFrame(rows)
