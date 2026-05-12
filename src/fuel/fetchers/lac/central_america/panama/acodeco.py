"""Panama Acodeco monthly historical fuel price fetcher.

Source: Autoridad de Protección al Consumidor y Defensa de la Competencia.
Listing: https://www.acodeco.gob.pa/inicio/estadisticas-precios/precios-2/

Acodeco publishes a single cumulative "HistoricoCombustible_Panama_<MES><YYYY>.pdf"
file that contains monthly average retail prices (USD/litre) in the
Panama City + San Miguelito metropolitan area since January 1998. The
filename's month-year reflects the latest observation included; one
download covers the entire history.

Pricing context: Panama caps retail prices via biweekly Decreto Ejecutivo
(state-managed), so we treat the series as carry_forward=true. Currency
is USD (Panama uses USD alongside the balboa). After 10 April 2017 only
ultra-low-sulfur diesel is sold; the modern table reports just three
products (Gasolina 91 Octanos, Gasolina 95 Octanos, Diesel Bajo Azufre)
which we extract here. Earlier years had additional products
(Gas Premium/Regular, Diesel Normal/Liviano, LPG) that we skip — the
table's column-x positions are stable but column populations shift
across regimes.

Extraction relies on pdfplumber's word boxes (extract_words) because
the PDF's alternating-row shading defeats extract_tables for half the
months. Rows are grouped by top-Y, then each price word is bucketed
by its x0 into one of three known column positions (~208, ~266, ~498).
"""

from __future__ import annotations

import io
import logging
import re
import unicodedata
from collections import defaultdict
from datetime import date

import pandas as pd
import pdfplumber
import urllib3

from core.http import make_session

# Acodeco's TLS chain trips certifi but is benign — silence the warning.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

_LISTING_URL = "https://www.acodeco.gob.pa/inicio/estadisticas-precios/precios-2/"
_PDF_HREF_RE = re.compile(
    r"href=\"(/inicio/wp-content/uploads/\d{4}/\d{2}/HistoricoCombustible_Panama_[^\"]+\.pdf)\"",
    re.IGNORECASE,
)
_BASE = "https://www.acodeco.gob.pa"

_COUNTRY = "Panama"
_CURRENCY = "USD"
_SOURCE_KEY = "pa_acodeco_monthly"

_DATE_RE = re.compile(r"^(\d{4})/(\d{2})$")
_FIRST_DATE = date(2017, 4, 1)  # post-regulation: 3 products only

# Column x0 positions empirically determined; ±10 tolerance.
_COLUMN_TOLERANCE = 12
_COLUMNS: list[tuple[int, str]] = [
    (208, "Gasolina 91 Octanos"),
    (266, "Gasolina 95 Octanos"),
    (498, "Diesel Bajo Azufre"),
]


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text).strip()


def _find_latest_pdf_url(html: str) -> str | None:
    """Return the most recent HistoricoCombustible_Panama URL from the listing."""
    matches = _PDF_HREF_RE.findall(html)
    if not matches:
        return None
    # Sort by the YYYY/MM upload path prefix — newest last.
    sorted_paths = sorted(matches)
    return _BASE + sorted_paths[-1]


def _bucket_column(x0: float) -> str | None:
    for col_x, product in _COLUMNS:
        if abs(x0 - col_x) <= _COLUMN_TOLERANCE:
            return product
    return None


def _parse_pdf(pdf_bytes: bytes) -> list[tuple[date, str, float]]:
    """Pull (date, product, price) triples from every monthly row."""
    out: list[tuple[date, str, float]] = []
    seen: set[tuple[date, str]] = set()

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            words = page.extract_words(keep_blank_chars=False)
            rows: dict[int, list[dict]] = defaultdict(list)
            for w in words:
                rows[round(w["top"])].append(w)

            for top in sorted(rows.keys()):
                sw = sorted(rows[top], key=lambda x: x["x0"])
                if not sw:
                    continue
                m = _DATE_RE.match(_normalize(sw[0]["text"]))
                if not m:
                    continue
                try:
                    obs_date = date(int(m.group(1)), int(m.group(2)), 1)
                except ValueError:
                    continue
                if obs_date < _FIRST_DATE:
                    continue
                for w in sw[1:]:
                    product = _bucket_column(w["x0"])
                    if product is None:
                        continue
                    try:
                        price = float(w["text"])
                    except ValueError:
                        continue
                    if price <= 0:
                        continue
                    key = (obs_date, product)
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append((obs_date, product, price))
    return out


def fetch_pa_acodeco(cutoff: date) -> pd.DataFrame | None:
    """Fetch Panama Acodeco monthly retail prices (USD/litre, metro area)."""
    session = make_session()
    # acodeco.gob.pa serves an incomplete TLS chain; cURL trusts it but
    # certifi does not. Disable verification per existing convention (see
    # src/fuel/fetchers/sar/south_asia/bangladesh/bpc.py).
    try:
        resp = session.get(_LISTING_URL, timeout=45, verify=False)
        resp.raise_for_status()
    except Exception:
        logger.exception("[pa_acodeco] Failed to fetch listing")
        return None

    pdf_url = _find_latest_pdf_url(resp.text)
    if pdf_url is None:
        logger.warning("[pa_acodeco] No HistoricoCombustible PDF on listing page")
        return None

    try:
        pdf_resp = session.get(pdf_url, timeout=60, verify=False)
        pdf_resp.raise_for_status()
    except Exception:
        logger.exception("[pa_acodeco] Failed to download %s", pdf_url)
        return None
    if not pdf_resp.content.startswith(b"%PDF"):
        logger.warning("[pa_acodeco] URL did not return a PDF: %s", pdf_url)
        return None

    triples = _parse_pdf(pdf_resp.content)
    if not triples:
        logger.warning("[pa_acodeco] No observations parsed from %s", pdf_url)
        return None

    rows: list[dict] = []
    for obs_date, product, price in triples:
        if obs_date <= cutoff:
            continue
        rows.append(
            {
                "observation_date": obs_date.strftime("%Y-%m-%d"),
                "country": _COUNTRY,
                "fuel_product": product,
                "price_local": round(price, 4),
                "currency": _CURRENCY,
                "source_key": _SOURCE_KEY,
                "unit": "L",
            }
        )

    if not rows:
        logger.info("[pa_acodeco] No new rows after cutoff %s", cutoff)
        return None

    out = (
        pd.DataFrame(rows)
        .sort_values(["observation_date", "fuel_product"])
        .reset_index(drop=True)
    )
    logger.info("[pa_acodeco] Returning %d rows (cutoff: %s)", len(out), cutoff)
    return out
