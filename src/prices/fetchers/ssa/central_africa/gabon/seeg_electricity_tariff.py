"""SEEG (Société d'Energie et d'Eau du Gabon) — household ("basse tension")
electricity tariff, Gabon.

SEEG is Gabon's state water/electricity utility. Its "Nos tarifs" page
(https://www.seeg-gabon.com/relation_client/tarifs) is server-rendered HTML
that links out to several PDF tariff schedules; the one labelled "Barèmes
révisés" ("Revised scales") is the full multi-page consumer+industrial price
grid. This fetcher re-fetches the HTML page live on every run (not a
hardcoded PDF URL) and follows whichever href currently carries that label,
so a future SEEG tariff revision that renames the PDF file is still picked
up automatically.

Only the "TARIFS BASSE TENSION" (low-voltage / residential) section is
scraped -- the same scope choice as the Côte d'Ivoire CIE fetcher
(cie_tariff.py) in this repo. The PDF's basse-tension section has two
tables:
  - "Tarif social national": a flat F/kWh rate for two small subscribed-
    power bands (1kW, 2kW), each capped at a monthly kWh ceiling.
  - "Tarif général national": for subscribed power <=15kW, a flat F/kWh
    rate per power tier (no fixed monthly charge); for >=18kW, a fixed
    monthly charge (F/kW) plus a F/kWh rate, banded by annual usage hours.
Measured live 2026-09-01 (PDF dated "valable à compter du : 01/01/2020"):
10 line items total (2 social + 5 general-low + 3 general-high).

STALENESS: the PDF's own cover page prints an explicit effective date
("valable à compter du : DD/MM/YYYY"), so this is NOT a hardcoded table --
every run re-downloads the current PDF and re-reads that date, and
`fetch_seeg_electricity_tariff_ga` refuses to ship if it can't find that
date or the basse-tension tables (logs a warning, returns None) rather than
silently falling back to a memorized layout. A loud warning is also logged
if the printed effective date is more than 2 years old relative to the
scrape date -- the tariffs page itself states rates are revised quarterly,
so a multi-year-old "current" PDF is a real signal worth a human's
attention even though it is genuinely what SEEG is publishing as current
right now.

Currency: XAF (Gabon; the PDF's own header prints bare "F" with no XOF/XAF
disambiguation -- confirmed XAF from countries.yaml, this is a Gabon-only
domestic tariff with no West-Africa multi-tenant ambiguity, unlike the
pharmacie_saintemarie_ga WooCommerce trap).

COICOP: 04.5.1 (electricity), narrow -- matches cie_tariff.py's convention.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import date

import pandas as pd
import pdfplumber

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_TARIFF_PAGE_URL = "https://www.seeg-gabon.com/relation_client/tarifs"
_COUNTRY = "Gabon"
_CURRENCY = "XAF"
_SOURCE_KEY = "seeg_electricity_tariff_ga"
_COICOP_CODE = "04.5.1"
_IDENT = ["source_key", "observation_date", "item_name"]

_PDF_LINK_RE = re.compile(
    r'<a href="([^"]+\.pdf)"[^>]*class="trf_pdf">\s*.*?cl_blec">\s*([^<]+?)\s*<',
    re.IGNORECASE | re.DOTALL,
)
_EFFECTIVE_DATE_RE = re.compile(
    r"valable\s*à\s*compter\s*du\s*:\s*(\d{2})\s*/\s*(\d{2})\s*/\s*(\d{4})"
)


def _nfc(text: str | None) -> str:
    """Unicode-normalize to NFC (precomposed accents). Both the site's HTML
    and pdfplumber's PDF text extraction were observed emitting NFD
    (decomposed, e.g. "e" + combining grave U+0300) for accented French
    text -- a literal accented substring check against un-normalized text
    silently never matches (confirmed: "barème" in "barèmes" was False
    because the two were in different normal forms), so every accented
    comparison in this module goes through this first."""
    return unicodedata.normalize("NFC", text) if text else (text or "")


def _find_baremes_pdf_url(html_text: str, page_url: str) -> str | None:
    """Locate the href for the link labelled "Barèmes révisés", tolerant of
    the timestamped filename changing on a future SEEG revision.

    BASE-HREF TRAP: the page carries `<base href="/">`, so its relative PDF
    hrefs ("med/trf/...") resolve against the SITE ROOT, not against the
    current page path. A plain urljoin(page_url, href) silently produces
    ".../relation_client/med/trf/..." instead of ".../med/trf/..." -- that
    wrong URL still returns HTTP 200 (a soft-404/stub page), so this only
    surfaces downstream as a PDF-parse failure ("No /Root object!") unless
    the <base> tag is honoured here."""
    from urllib.parse import urljoin

    base_match = re.search(r'<base\s+href="([^"]*)"', html_text, re.IGNORECASE)
    effective_base = urljoin(page_url, base_match.group(1)) if base_match else page_url

    for href, label in _PDF_LINK_RE.findall(_nfc(html_text)):
        if "barème" in _nfc(label).lower() or "bareme" in _nfc(label).lower():
            return urljoin(effective_base, href)
    return None


def _parse_multiline(cell: str | None) -> list[str]:
    if not cell:
        return []
    return [line.strip() for line in cell.split("\n") if line.strip()]


def _parse_fcfa(text: str) -> float | None:
    cleaned = text.strip().replace(" ", "").replace("\xa0", "").replace(",", ".")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _extract_effective_date(first_page_text: str) -> date | None:
    m = _EFFECTIVE_DATE_RE.search(_nfc(first_page_text))
    if not m:
        return None
    day, month, year = m.groups()
    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        return None


def _extract_social_rows(pdf: "pdfplumber.PDF", obs_date: date) -> list[dict]:
    """'TARIFS BASSE TENSION' page carrying 'Tarif social national'."""
    rows: list[dict] = []
    for page in pdf.pages:
        text = _nfc(page.extract_text() or "")
        if "TARIFS BASSE TENSION" not in text or "Tarif social national" not in text:
            continue
        for table in page.extract_tables():
            header_row = next(
                (
                    r
                    for r in table
                    if r and r[0] and "Tarif social national" in _nfc(r[0])
                ),
                None,
            )
            if header_row is None:
                continue
            idx = table.index(header_row)
            data_row = table[idx + 1] if idx + 1 < len(table) else None
            if not data_row:
                continue
            bands = _parse_multiline(data_row[0])
            prices = _parse_multiline(data_row[2]) if len(data_row) > 2 else []
            limits = _parse_multiline(data_row[3]) if len(data_row) > 3 else []
            for band, price_txt, limit in zip(bands, prices, limits):
                price = _parse_fcfa(price_txt)
                if price is None:
                    continue
                item_name = (
                    f"SEEG Tarif social national, {band} (limite {limit} kWh/mois)"
                )
                row = {
                    "observation_date": obs_date.isoformat(),
                    "period_kind": "effective_from",
                    "country": _COUNTRY,
                    "source_key": _SOURCE_KEY,
                    "coicop_code": _COICOP_CODE,
                    "item_name": item_name,
                    "price_local": price,
                    "currency": _CURRENCY,
                    "unit": "kWh",
                    "source_url": _TARIFF_PAGE_URL,
                    "notes": "Basse tension, tarif social national (subsidised low-power band)",
                    "scrape_ts": get_scrape_ts(),
                    "observation_hash": None,
                }
                row["observation_hash"] = make_hash(row, _IDENT)
                rows.append(row)
        break
    return rows


def _extract_general_rows(pdf: "pdfplumber.PDF", obs_date: date) -> list[dict]:
    """'TARIFS BASSE TENSION' page carrying 'Tarif général national'."""
    rows: list[dict] = []
    for page in pdf.pages:
        text = _nfc(page.extract_text() or "")
        if "TARIFS BASSE TENSION" not in text or "Tarif général national" not in text:
            continue
        for table in page.extract_tables():
            header_row = next(
                (
                    r
                    for r in table
                    if r and r[0] and "Tarif général national" in _nfc(r[0])
                ),
                None,
            )
            if header_row is None:
                continue
            idx = table.index(header_row)
            # Low-power block: header band row + a following price-only row
            # (labels in one row, "" placeholders, prices on the NEXT row).
            for j in range(idx + 1, len(table)):
                r = table[j]
                if not r or not r[0]:
                    continue
                if "<= 15 kW" in r[0] or "<=15" in r[0].replace(" ", ""):
                    bands = _parse_multiline(r[0])[
                        1:
                    ]  # drop the "Puissance souscrite <=15kW" label
                    prices = []
                    if j + 1 < len(table) and table[j + 1] and len(table[j + 1]) > 2:
                        prices = _parse_multiline(table[j + 1][2])
                    for band, price_txt in zip(bands, prices):
                        price = _parse_fcfa(price_txt)
                        if price is None:
                            continue
                        item_name = (
                            f"SEEG Tarif général national, puissance souscrite {band}"
                        )
                        row = {
                            "observation_date": obs_date.isoformat(),
                            "period_kind": "effective_from",
                            "country": _COUNTRY,
                            "source_key": _SOURCE_KEY,
                            "coicop_code": _COICOP_CODE,
                            "item_name": item_name,
                            "price_local": price,
                            "currency": _CURRENCY,
                            "unit": "kWh",
                            "source_url": _TARIFF_PAGE_URL,
                            "notes": "Basse tension, tarif général, puissance souscrite <=15kW (flat F/kWh, no fixed charge)",
                            "scrape_ts": get_scrape_ts(),
                            "observation_hash": None,
                        }
                        row["observation_hash"] = make_hash(row, _IDENT)
                        rows.append(row)
                elif ">= 18 kW" in r[0] or ">=18" in r[0].replace(" ", ""):
                    labels = _parse_multiline(r[0])[
                        1:
                    ]  # drop "Puissance souscrite >=18kW"
                    prices = _parse_multiline(r[2]) if len(r) > 2 else []
                    for label, price_txt in zip(labels, prices):
                        price = _parse_fcfa(price_txt)
                        if price is None:
                            continue
                        item_name = f"SEEG Tarif général national, puissance >=18kW, {label} (F/kWh)"
                        row = {
                            "observation_date": obs_date.isoformat(),
                            "period_kind": "effective_from",
                            "country": _COUNTRY,
                            "source_key": _SOURCE_KEY,
                            "coicop_code": _COICOP_CODE,
                            "item_name": item_name,
                            "price_local": price,
                            "currency": _CURRENCY,
                            "unit": "kWh",
                            "source_url": _TARIFF_PAGE_URL,
                            "notes": "Basse tension, tarif général, puissance souscrite >=18kW, variable (F/kWh) component only -- excludes the separate F/kW fixed monthly charge",
                            "scrape_ts": get_scrape_ts(),
                            "observation_hash": None,
                        }
                        row["observation_hash"] = make_hash(row, _IDENT)
                        rows.append(row)
        break
    return rows


def fetch_seeg_electricity_tariff_ga(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_TARIFF_PAGE_URL, timeout=30)
    if resp.status_code != 200:
        logger.warning(
            "[%s] HTTP %d for %s", _SOURCE_KEY, resp.status_code, _TARIFF_PAGE_URL
        )
        return None

    pdf_url = _find_baremes_pdf_url(resp.text, _TARIFF_PAGE_URL)
    if not pdf_url:
        logger.warning(
            "[%s] Could not find a 'Barèmes révisés' PDF link on %s",
            _SOURCE_KEY,
            _TARIFF_PAGE_URL,
        )
        return None

    pdf_resp = session.get(pdf_url, timeout=30)
    if pdf_resp.status_code != 200:
        logger.warning(
            "[%s] HTTP %d for %s", _SOURCE_KEY, pdf_resp.status_code, pdf_url
        )
        return None
    if not pdf_resp.content.startswith(b"%PDF"):
        # Seen in practice: a wrongly-resolved URL (see the <base href>
        # trap above) 200s with a small HTML stub instead of a PDF.
        logger.warning(
            "[%s] %s did not return a PDF (got %d bytes, content-type %s)",
            _SOURCE_KEY,
            pdf_url,
            len(pdf_resp.content),
            pdf_resp.headers.get("content-type"),
        )
        return None

    import io

    with pdfplumber.open(io.BytesIO(pdf_resp.content)) as pdf:
        effective_date = _extract_effective_date(pdf.pages[0].extract_text() or "")
        if effective_date is None:
            logger.warning(
                "[%s] Could not find 'valable à compter du' effective date in %s",
                _SOURCE_KEY,
                pdf_url,
            )
            return None
        if effective_date <= cutoff:
            return None

        age_days = (date.today() - effective_date).days
        if age_days > 730:
            logger.warning(
                "[%s] Tariff PDF's own effective date is %s (%d days old) -- "
                "the tariffs page states rates are revised quarterly; this "
                "may be a genuinely stable rate or a sign the PDF link "
                "logic broke. Shipping it anyway since it is what SEEG "
                "currently publishes as the live schedule.",
                _SOURCE_KEY,
                effective_date.isoformat(),
                age_days,
            )

        rows = _extract_social_rows(pdf, effective_date) + _extract_general_rows(
            pdf, effective_date
        )

    if not rows:
        logger.warning(
            "[%s] No basse-tension tariff rows parsed from %s -- PDF layout "
            "may have changed",
            _SOURCE_KEY,
            pdf_url,
        )
        return None

    return pd.DataFrame(rows)
