"""Puerto Rico -- LUMA Energy residential electricity tariff, snapshot.

LUMA (the transmission/distribution operator; rates are actually set by the
Negociado de Energía de Puerto Rico / PR Energy Bureau, LUMA just publishes
them) hosts a "Libro de Tarifas del Servicio Eléctrico en Puerto Rico" PDF
linked from https://www.lumapr.com/tarifas/. The fetcher re-resolves the
PDF link from that page each run rather than hardcoding a filename --
observed live 2026-09-06 as
"FY2027-Tariff-Book-Modifications_Spanish.pdf" (year-stamped, will change).

The PDF (85 pages, genuinely text-based -- pdfplumber recovers clean text,
not scanned) opens with three genuinely-residential household tariffs, each
a fixed-format prose block, not a table:
    GRS  "Servicio Residencial General"           -- the standard rate
    LRS  "Servicio Residencial Especial"           -- Nutritional Assistance
                                                       Program households
    RH3  "Servicio Residencial Proyectos Públicos" -- public-housing projects
e.g. (GRS):
    Cargo Mensual del Cliente: $8.00
    Cargo Mensual por Energía: $0.08648 por kWh por los primeros 425 kWh...
This fetcher extracts, for EACH of the three designations, the fixed
monthly customer charge and the first-tier (<=425 kWh/month) energy
charge, via regex anchored to that designation's section (located by
"DESIGNACIÓN:\n<CODE>" and reading forward to the next "DESIGNACI..."
heading, so a future reordering of sections doesn't silently pick up the
wrong tariff's numbers). Other designations in the same book (USSL, PPBB,
GSS, etc.) are commercial/industrial/unmetered classes, out of scope for
the household PPP basket -- same convention as sp_group_tariff.py, which
excludes Singapore's High-Tension/EHT supplies for the same reason.

Six rows are emitted per run (customer charge + energy charge x 3
designations). All are the tariffs' BASE rate only -- each is also subject
to ~12 riders (fuel-purchase adjustment FCA, purchased-power PPCA,
subsidies, etc.) that are the dominant driver of the actual bill and
change monthly; those are not captured here (no stable single "current"
value exists for them -- each has its own separately-published rider
schedule). Recorded as a known limitation rather than guessed at. The
second energy-charge tier (consumption above 425 kWh/month) is likewise
not captured -- GRS and LRS/RH3 have DIFFERENT tier-1 rates but the same
$0.08648 tier-2 rate, so tier-1 is the rate that actually distinguishes
the three classes and is the one kept.

No prior-tariff archive was found on the page (only the current book is
linked) -- like the Burkina Faso Orange tariff, this snapshots the CURRENT
book each run (period_kind: effective_from). The book's own text does not
carry a clean effective date field extractable from pdfplumber's text
layer (the "Fecha de entrada en vigor:" line renders blank -- likely a
form-field or adjacent-cell value pdfplumber does not recover) so
effective_from is approximated from the upload path's year-month
(.../uploads/2026/07/... -> 2026-07-01).

Currency: USD (matches countries.yaml; PR's own currency, not a
mislabeled foreign symbol).

coicop_classification: source_curated -- COICOP 04.5.1 (electricity),
narrow single-class source.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from io import BytesIO

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_TARIFF_PAGE = "https://www.lumapr.com/tarifas/"
_COUNTRY = "Puerto Rico"
_CURRENCY = "USD"
_SOURCE_KEY = "pr_luma_tariff"
_COICOP_CODE = "04.5.1.0"
_IDENT = ["source_key", "observation_date", "item_name"]

_PDF_LINK_RE = re.compile(r'https?://[^"\']+Tariff-Book[^"\']+\.pdf', re.I)
_CUSTOMER_CHARGE_RE = re.compile(
    r"Cargo Mensual del Cliente:\s*\$?\s*([\d,]+\.\d+)", re.I
)
_ENERGY_CHARGE_RE = re.compile(
    r"Cargo Mensual por Energ[ií]a:\s*\$?\s*([\d,]+\.\d+)\s*por kWh", re.I
)
_YEAR_MONTH_RE = re.compile(r"/uploads/(\d{4})/(\d{2})/")

_DESIGNATIONS = {
    "GRS": "Electricity tariff, residential general (GRS)",
    "LRS": "Electricity tariff, residential special/nutrition-assistance (LRS)",
    "RH3": "Electricity tariff, residential public housing (RH3)",
}


def _extract_section(full_text: str, code: str) -> str | None:
    marker = f"DESIGNACIÓN:\n{code}"
    marker_ascii = f"DESIGNACION:\n{code}"
    start = full_text.find(marker)
    if start < 0:
        start = full_text.find(marker_ascii)
    if start < 0:
        return None
    next_designacion = full_text.find("DESIGNACI", start + len(marker))
    end = next_designacion if next_designacion > 0 else start + 3000
    return full_text[start:end]


def fetch_pr_luma_tariff(cutoff: date) -> pd.DataFrame | None:
    session = get_session()

    try:
        page_resp = session.get(_TARIFF_PAGE, timeout=60)
        page_resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] tariff page fetch failed: %s", _SOURCE_KEY, exc)
        return None

    m = _PDF_LINK_RE.search(page_resp.text)
    if not m:
        logger.warning("[%s] no Tariff Book PDF link found on %s", _SOURCE_KEY, _TARIFF_PAGE)
        return None
    pdf_url = m.group(0)

    ym = _YEAR_MONTH_RE.search(pdf_url)
    effective_from = date(int(ym.group(1)), int(ym.group(2)), 1) if ym else date.today().replace(day=1)
    if effective_from <= cutoff:
        logger.info("[%s] no new release past cutoff=%s", _SOURCE_KEY, cutoff)
        return None

    try:
        pdf_resp = session.get(pdf_url, timeout=90)
        pdf_resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] PDF fetch failed: %s", _SOURCE_KEY, exc)
        return None

    import pdfplumber

    full_text = ""
    try:
        with pdfplumber.open(BytesIO(pdf_resp.content)) as pdf:
            for page in pdf.pages[:10]:
                full_text += (page.extract_text() or "") + "\n"
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] PDF parse failed: %s", _SOURCE_KEY, exc)
        return None

    items: list[tuple[str, float, str]] = []
    for code, label in _DESIGNATIONS.items():
        section_text = _extract_section(full_text, code)
        if section_text is None:
            logger.warning("[%s] %s section not found in %s", _SOURCE_KEY, code, pdf_url)
            continue
        customer_m = _CUSTOMER_CHARGE_RE.search(section_text)
        energy_m = _ENERGY_CHARGE_RE.search(section_text)
        if not customer_m or not energy_m:
            logger.warning("[%s] rate figures not found in %s section", _SOURCE_KEY, code)
            continue
        items.append((f"{label}, customer charge", float(customer_m.group(1).replace(",", "")), "month"))
        items.append((f"{label}, energy charge (first 425 kWh/mo)", float(energy_m.group(1).replace(",", "")), "kWh"))

    if not items:
        logger.warning("[%s] no rate figures parsed from any designation", _SOURCE_KEY)
        return None

    ts = get_scrape_ts()
    rows: list[dict] = []
    for item_name, price, unit in items:
        row = {
            "observation_date": effective_from.isoformat(),
            "period_kind": "effective_from",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP_CODE,
            "item_name": item_name,
            "price_local": price,
            "currency": _CURRENCY,
            "unit": unit,
            "source_url": pdf_url,
            "notes": "GRS (Servicio Residencial General) base rate only, riders (FCA/PPCA/subsidies) not included",
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
