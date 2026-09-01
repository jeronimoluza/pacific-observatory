"""Yap State Public Service Corporation (YSPSC) -- electricity tariff for Yap
Main Island.

YSPSC posts its current tariff notice as a PDF linked directly from the
homepage (``yspsc.org``), filename date-stamped (e.g.
``New Tariff Announcement.5.27.26.Final.pdf``). This fetcher always resolves
whichever link on the homepage matches "Tariff Announcement" -- it never
hardcodes the dated filename -- so a future re-announcement is picked up
automatically without a code change; that live re-resolution is the
staleness guard (see onboarding-skill rule #3), there is no hardcoded table.

The PDF renders one clean table (pdfplumber ``extract_table()`` reads it
without OCR):

    CUSTOMER CATEGORIES | RES TIER1 | RES TIER2 | COMM TIER1 | COMM TIER2 | GOVT
    NON-FUEL COST (NFC) | $0.16     | $0.24     | $0.27      | $0.31      | $0.53
    FIXED MONTHLY CHARGE| $5 (merged across both Residential columns)| $20 | $40 | $40

Only NFC (non-fuel cost per kWh) and FMC (fixed monthly charge) are
published as fixed numbers -- the third component, VFC (variable fuel
cost), is explicitly "***" in the source PDF because it is recomputed every
month from that month's fuel cost and is not disclosed in this notice.
TARIFF PER KWH = NFC + VFC, so these NFC rows are a *partial* per-kWh rate,
not the full bill rate -- flagged in YAML notes, same class of caveat as
Vanuatu's URA tariff (administered rate, not a shelf price).

Reconnection fees ($125 delinquent / $40 non-delinquent, prose-only, not in
the table) are also captured as flat one-time tariff items.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd
import pdfplumber

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Micronesia, Fed. Sts."
_CURRENCY = "USD"
_SOURCE_KEY = "fm_yspsc_electricity_tariff"
_COICOP = "04.5.1"
_STATE = "Yap"
_HOMEPAGE = "https://yspsc.org/"
_IDENT = ["source_key", "effective_from", "item_name"]

_EFFECTIVE_RE = re.compile(r"Effective Date\s*:\s*([A-Za-z]+ \d{1,2},\s*\d{4})")

_NFC_LABELS = [
    "NFC -- Residential Tier 1 (0-100 kWh)",
    "NFC -- Residential Tier 2 (>100 kWh)",
    "NFC -- Commercial Tier 1 (0-300 kWh)",
    "NFC -- Commercial Tier 2 (>300 kWh)",
    "NFC -- Government (all usage)",
]
_FMC_LABELS = [
    "FMC -- Residential (all tiers)",
    None,  # merged cell, no second value
    "FMC -- Commercial Tier 1",
    "FMC -- Commercial Tier 2",
    "FMC -- Government",
]


def _find_pdf_url(session) -> str | None:
    resp = session.get(_HOMEPAGE, timeout=30)
    resp.raise_for_status()
    m = re.search(r'href="([^"]*Tariff Announcement[^"]*\.pdf)"', resp.text, re.I)
    if not m:
        return None
    href = m.group(1)
    return href if href.startswith("http") else _HOMEPAGE + href


def _price(text: str | None) -> float | None:
    if not text:
        return None
    text = text.replace("$", "").replace(",", "").strip()
    try:
        val = float(text)
    except ValueError:
        return None
    return val if val > 0 else None


def fetch_fm_yspsc_electricity_tariff(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    pdf_url = _find_pdf_url(session)
    if pdf_url is None:
        logger.warning(
            "[%s] no 'Tariff Announcement' PDF link found on %s", _SOURCE_KEY, _HOMEPAGE
        )
        return None

    resp = session.get(pdf_url, timeout=30)
    resp.raise_for_status()

    with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
        # Rate table + "Effective Date" are on page 1; the reconnection-fee
        # prose is on page 3 -- join all pages so both regex passes work.
        full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)
        table = pdf.pages[0].extract_table()

    m = _EFFECTIVE_RE.search(full_text)
    if not m:
        logger.warning(
            "[%s] could not find 'Effective Date' in %s", _SOURCE_KEY, pdf_url
        )
        return None
    effective_from = pd.to_datetime(m.group(1)).date()
    if effective_from <= cutoff:
        logger.info(
            "[%s] no new tariff (effective=%s, cutoff=%s)",
            _SOURCE_KEY,
            effective_from,
            cutoff,
        )
        return None

    if not table:
        logger.warning("[%s] no table extracted from %s", _SOURCE_KEY, pdf_url)
        return None

    nfc_row = next(
        (r for r in table if r and r[0] and "NON-FUEL COST" in r[0].upper()), None
    )
    fmc_row = next(
        (r for r in table if r and r[0] and "FIXED MONTHLY CHARGE" in r[0].upper()),
        None,
    )
    if nfc_row is None or fmc_row is None:
        logger.warning(
            "[%s] NFC/FMC row not found in extracted table -- layout may have changed",
            _SOURCE_KEY,
        )
        return None

    items: list[tuple[str, float | None, str]] = []
    for label, cell in zip(_NFC_LABELS, nfc_row[1:]):
        items.append((label, _price(cell), "USD/kWh"))
    for label, cell in zip(_FMC_LABELS, fmc_row[1:]):
        if label is None:
            continue
        items.append((label, _price(cell), "USD/month"))

    # Reconnection fees -- published as prose, not in the table.
    recon_delinquent = re.search(r"increased from \$\d+ to \$([\d,.]+)", full_text)
    recon_nondelinquent = re.search(
        r"not delinquent.*?remain at \$([\d,.]+)", full_text, re.S
    )
    if recon_delinquent:
        items.append(
            (
                "Reconnection fee -- delinquent account",
                _price(recon_delinquent.group(1)),
                "USD/event",
            )
        )
    if recon_nondelinquent:
        items.append(
            (
                "Reconnection fee -- non-delinquent, by request",
                _price(recon_nondelinquent.group(1)),
                "USD/event",
            )
        )

    ts = get_scrape_ts()
    rows = []
    for item_name, price_local, unit in items:
        if price_local is None:
            continue
        row = {
            "observation_date": effective_from.isoformat(),
            "period_kind": "effective_from",
            "country": _COUNTRY,
            "subnational_area": _STATE,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP,
            "item_name": item_name,
            "price_local": price_local,
            "currency": _CURRENCY,
            "unit": unit,
            "source_url": pdf_url,
            "notes": (
                "NFC (non-fuel cost) only -- the source's own per-kWh tariff "
                "also includes an undisclosed Variable Fuel Cost (VFC) "
                "recomputed monthly; this row is a partial administered "
                "rate, not the full bill rate."
                if "NFC" in item_name
                else None
            ),
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows) if rows else None
