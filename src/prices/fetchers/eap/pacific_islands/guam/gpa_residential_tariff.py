"""Guam Power Authority (GPA) -- Schedule "R" (Residential Service) electricity
tariff.

GPA's ``/rates`` Wix page lists ~20 rate-schedule PDFs (Schedules R, D, G, J,
P, I, H, S, K, L, M, F, N, A, B, C, Z -- residential, commercial, industrial,
government, lighting, net-metering, and rider schedules) as opaque
``*.usrfiles.com/ugd/<hash>.pdf`` links with no schedule letter in the URL or
surrounding link text. The schedule identity only exists inside each PDF's
own header ("Rate Schedule \"R\"" / "SCHEDULE \"R\" / Residential Service").
The fetcher therefore downloads every linked PDF and keeps only the one
whose header names Schedule R, rather than guessing from the URL.

Schedule R's body is prose, not a ruled table (Non-Fuel Energy Charge is a
two-tier per-kWh rate, plus a flat monthly Customer Charge and two small
per-kWh riders) -- rates are pulled with targeted regexes against known field
labels, the same "prose tariff" pattern as smart_tariff.py (Cambodia), not a
pdfplumber table extraction.

Scope: Schedule R (Residential) only, for this pass. The other ~19 schedules
(Commercial/Industrial/Demand/Government/Lighting/Net-Metering/Rider
schedules A-Z) are linked from the same page in the same PDF shape and would
be natural follow-on sources, out of scope here.

Currency: USD (Guam is a US territory; GPA rates are quoted in whole and
fractional USD cents, e.g. $0.08086/kWh -- five decimal places is the
source's own published precision for its non-fuel energy charge, not a
parsing artifact).
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

_PAGE_URL = "https://www.guampowerauthority.com/rates"
_COUNTRY = "Guam"
_CURRENCY = "USD"
_SOURCE_KEY = "gu_gpa_residential_tariff"
_COICOP = "04.5.1.0"
_IDENT = ["source_key", "effective_from", "item_name"]

_PDF_HREF_RE = re.compile(r'href="(https://[a-f0-9-]+\.usrfiles\.com/ugd/[^"]+\.pdf)"')
_SCHEDULE_R_RE = re.compile(r'Rate Schedule\s*"R"|SCHEDULE\s*"R"\s*\n?\s*Residential Service')
_EFFECTIVE_RE = re.compile(
    r"Effective with meters read\s*\n?\s*on and after ([A-Za-z]+ \d{1,2}, \d{4})"
)

_FIELD_PATTERNS: list[tuple[str, re.Pattern, str | None]] = [
    (
        "Non-Fuel Energy Charge - First 500 kWh/month",
        re.compile(r"First 500 kWh per month.*?per kWh\s*\$([\d.]+)"),
        "kWh",
    ),
    (
        "Non-Fuel Energy Charge - Over 500 kWh/month",
        re.compile(r"Over 500 kWh per month.*?per kWh\s*\$([\d.]+)"),
        "kWh",
    ),
    (
        "Customer Charge",
        re.compile(r"Customer Charge\s*-\s*per month\s*\$([\d.]+)"),
        "month",
    ),
    (
        "Insurance Charge",
        re.compile(r"insurance charge of\s*\$([\d.]+)\s*per kWh"),
        "kWh",
    ),
    (
        "Emergency Water Well and Wastewater Charge",
        re.compile(r"Wastewater charge of\s*\$([\d.]+)\s*per kWh"),
        "kWh",
    ),
]


def _find_pdf_urls(html: str) -> list[str]:
    return sorted(set(_PDF_HREF_RE.findall(html)))


def fetch_gu_gpa_residential_tariff(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    try:
        page = session.get(_PAGE_URL, timeout=30)
        page.raise_for_status()
    except Exception:
        logger.exception("[%s] could not load %s", _SOURCE_KEY, _PAGE_URL)
        return None

    pdf_urls = _find_pdf_urls(page.text)
    if not pdf_urls:
        logger.warning(
            "[%s] no rate-schedule PDF links found on %s -- page layout may "
            "have changed",
            _SOURCE_KEY,
            _PAGE_URL,
        )
        return None

    schedule_r_text: str | None = None
    schedule_r_url: str | None = None
    for url in pdf_urls:
        try:
            resp = session.get(url, timeout=60)
            resp.raise_for_status()
            with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
                text = "\n".join(p.extract_text() or "" for p in pdf.pages[:2])
        except Exception:
            logger.info("[%s] skipping unreadable PDF %s", _SOURCE_KEY, url)
            continue
        if _SCHEDULE_R_RE.search(text):
            schedule_r_text = text
            schedule_r_url = url
            break

    if schedule_r_text is None:
        logger.warning(
            "[%s] none of %d linked PDFs matched Schedule R's header -- "
            "site layout may have changed",
            _SOURCE_KEY,
            len(pdf_urls),
        )
        return None

    m = _EFFECTIVE_RE.search(schedule_r_text)
    if not m:
        logger.warning(
            "[%s] found Schedule R PDF but could not parse its effective date",
            _SOURCE_KEY,
        )
        return None
    effective_from = pd.to_datetime(m.group(1), format="%B %d, %Y").date()
    if effective_from <= cutoff:
        logger.info(
            "[%s] effective_from=%s not newer than cutoff=%s",
            _SOURCE_KEY,
            effective_from,
            cutoff,
        )
        return None

    ts = get_scrape_ts()
    rows: list[dict] = []
    for item_name, pattern, unit in _FIELD_PATTERNS:
        fm = pattern.search(schedule_r_text)
        if not fm:
            logger.info(
                "[%s] field %r not found in Schedule R text -- skipping",
                _SOURCE_KEY,
                item_name,
            )
            continue
        try:
            price_local = float(fm.group(1))
        except ValueError:
            continue
        if price_local <= 0:
            continue
        row = {
            "observation_date": effective_from.isoformat(),
            "period_kind": "effective_from",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": f"Electricity tariff - Residential (Schedule R) - {item_name}",
            "price_local": price_local,
            "currency": _CURRENCY,
            "unit": unit,
            "coicop_code": _COICOP,
            "effective_from": effective_from.isoformat(),
            "source_url": schedule_r_url,
            "notes": (
                "GPA Schedule \"R\" (Residential Service) tariff, read from "
                "the rate-schedule PDF's own prose text (not a ruled table)."
            ),
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    if not rows:
        logger.warning(
            "[%s] Schedule R PDF matched but no known rate fields parsed",
            _SOURCE_KEY,
        )
        return None

    return pd.DataFrame(rows)
