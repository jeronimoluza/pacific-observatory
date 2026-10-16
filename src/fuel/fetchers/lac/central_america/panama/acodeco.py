"""Panama Acodeco monthly historical fuel price fetcher.

Source: Autoridad de Protección al Consumidor y Defensa de la Competencia.
Listing: https://www.acodeco.gob.pa/estadistica-precio/

Acodeco publishes a cumulative "Historico_Combustible_<YYYY>.pdf" (formerly
"HistoricoCombustible_Panama_<MES><YYYY>.pdf") titled "PRECIO PROMEDIO
MENSUAL EN LITROS ... EN LOS DISTRITOS DE PANAMÁ Y SAN MIGUELITO, EN
ESTACIONES DE EXPENDIO DE COMBUSTIBLE": monthly average retail pump prices
(USD/litre) surveyed at service stations, January 1998 onwards. One
download covers the entire history.

Pricing context: Panama caps retail prices via biweekly Decreto Ejecutivo
(state-managed), so we treat the series as carry_forward=true. After
10 April 2017 only ultra-low-sulfur diesel is sold; from then on only
Gasolina 91/95 Octanos and Diesel Bajo (en) Azufre carry values, which is
what we extract.

Extraction relies on pdfplumber's word boxes (extract_words) because the
PDF's alternating-row shading defeats extract_tables for half the months.
Column positions are read from each page's two-line header (one column per
"Gasolina"/"Diesel"/"Gas" anchor) rather than fixed x, since columns move
when Acodeco adds one (e.g. Gasolina 87 Octanos in 2026). Each price word
goes to the column whose header centre is nearest.
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

_LISTING_URL = "https://www.acodeco.gob.pa/estadistica-precio/"
_PDF_HREF_RE = re.compile(
    r"href=\"((?:https://www\.acodeco\.gob\.pa)?(?:/inicio)?/wp-content/uploads/"
    r"\d{4}/\d{2}/Historico_?Combustible[^\"]*\.pdf)\"",
    re.IGNORECASE,
)
_BASE = "https://www.acodeco.gob.pa"

_COUNTRY = "Panama"
_CURRENCY = "USD"
_SOURCE_KEY = "pa_acodeco_monthly"

_DATE_RE = re.compile(r"^(\d{4})/(\d{2})$")
_FIRST_DATE = date(2017, 4, 1)  # post-regulation: 3 products only

_ANCHORS = {"Gasolina", "Diesel", "Gas"}
_MIN_ANCHORS = 5  # the chart legend under the table repeats 2-3 anchors
_ROW_TOLERANCE = 2  # pt
_HEADER_GAP = 30  # second header line sits ~15pt below the first
# Header label (both lines joined) -> YAML product name. Other columns
# (Premiun, Regular, Normal, Liviano, LPG) are empty after 2017-04.
_PRODUCTS = {
    "Gasolina 91 Octanos": "Gasolina 91 Octanos",
    "Gasolina 95 Octanos": "Gasolina 95 Octanos",
    "Gasolina 87 Octanos": "Gasolina 87 Octanos",
    "Diesel Bajo en Azufre": "Diesel Bajo Azufre",
    "Diesel Bajo Azufre": "Diesel Bajo Azufre",
}


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text).strip()


def _find_latest_pdf_url(html: str) -> str | None:
    """Return the most recent Historico combustible PDF URL from the listing."""
    paths = {m.removeprefix(_BASE) for m in _PDF_HREF_RE.findall(html)}
    if not paths:
        return None
    # The /YYYY/MM/ upload prefix sorts chronologically — newest last.
    return _BASE + sorted(paths)[-1]


def _header_columns(rows: dict[int, list[dict]]) -> list[tuple[float, str]]:
    """Return (x-centre, label) per table column from the page header."""
    tops = sorted(rows)
    for i, top in enumerate(tops):
        line = sorted(rows[top], key=lambda w: w["x0"])
        anchors = [w for w in line if _normalize(w["text"]) in _ANCHORS]
        if len(anchors) < _MIN_ANCHORS:
            continue
        # Line 1: each anchor plus the words after it ("Gasolina 91", "Diesel
        # Bajo"); line-2 words join the line-1 column whose centre is nearest.
        cols: list[tuple[float, list[str]]] = []
        for j, anchor in enumerate(anchors):
            hi = anchors[j + 1]["x0"] if j + 1 < len(anchors) else float("inf")
            words = [w for w in line if anchor["x0"] <= w["x0"] < hi]
            centre = (words[0]["x0"] + words[-1]["x1"]) / 2
            cols.append((centre, [_normalize(w["text"]) for w in words]))
        for t in tops[i + 1 :]:
            if t - top > _HEADER_GAP:
                break
            for w in sorted(rows[t], key=lambda w: w["x0"]):
                text = _normalize(w["text"])
                if text.startswith("Año"):
                    continue
                centre = (w["x0"] + w["x1"]) / 2
                min(cols, key=lambda c: abs(c[0] - centre))[1].append(text)
        return [(centre, " ".join(parts)) for centre, parts in cols]
    return []


def _parse_pdf(pdf_bytes: bytes) -> list[tuple[date, str, float]]:
    """Pull (date, product, price) triples from every monthly row."""
    out: list[tuple[date, str, float]] = []
    seen: set[tuple[date, str]] = set()

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            words = page.extract_words(keep_blank_chars=False)
            # Cluster by top with a tolerance: a row's words can sit a
            # fraction of a point apart and straddle a rounding boundary
            # (2022/06 in the 2026 PDF).
            rows: dict[int, list[dict]] = defaultdict(list)
            anchor_top = None
            for w in sorted(words, key=lambda w: w["top"]):
                if anchor_top is None or w["top"] - anchor_top > _ROW_TOLERANCE:
                    anchor_top = w["top"]
                rows[round(anchor_top)].append(w)
            columns = _header_columns(rows)
            if not columns:
                continue

            for top in sorted(rows.keys()):
                sw = sorted(rows[top], key=lambda x: x["x0"])
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
                    centre = (w["x0"] + w["x1"]) / 2
                    _, label = min(columns, key=lambda c: abs(c[0] - centre))
                    product = _PRODUCTS.get(label)
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
                "city": "Panamá y San Miguelito",
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
