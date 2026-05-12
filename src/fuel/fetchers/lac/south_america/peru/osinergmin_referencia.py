"""Peru Osinergmin weekly reference-price (PR1) fetcher.

Source page: https://www.osinergmin.gob.pe/seccion/institucional/Paginas/
             VisorPreciosReferencia.aspx?Codigo={YYYY}

Each weekly publication is a 2-page PDF at:
  https://www.osinergmin.gob.pe/seccion/centro_documental/gart/
  PreciosReferencia/PrecioReferenciaDDMMYYYY.pdf

The first page contains four reference-price tables (PR1, ex-plant, no
taxes / no commercial margin). Layout is stable across 2023→present:

  ┌ PR1 main row (9 products) ─ Soles/galón ─────────────────────────┐
  │ GLP | Gas.Premium | Gas.Regular | Gas.84 | Turbo |               │
  │ Diésel B5 BA | Diésel B5 AA | Petr.Ind.6 | Petr.Ind.500          │
  └──────────────────────────────────────────────────────────────────┘
  ┌ GLP per-kg ─ Soles/Kg ──────────────────────────────────────────┐
  │ GLP 70/30                                                        │
  └──────────────────────────────────────────────────────────────────┘
  ┌ Gasohol section ─ 8 numbers ────────────────────────────────────┐
  │ [USD/Bl: GasoholP, GasoholR, Gasohol84] then                    │
  │ [Soles/Gln: GasoholP, GasoholR, Gasohol84] then                 │
  │ [USD/Bl: AlcCarb, Soles/Gln: AlcCarb]                           │
  └──────────────────────────────────────────────────────────────────┘
  ┌ Diésel 2 + Biodiesel ─ 6 numbers ───────────────────────────────┐
  │ [USD/Bl: D2 BA, D2 AA] then [Soles/Gln: D2 BA, D2 AA] then      │
  │ [USD/Bl: Biodiesel] then [Soles/Gln: Biodiesel]                 │
  └──────────────────────────────────────────────────────────────────┘

PDF text rendering separates every character with a small horizontal
gap; we reassemble tokens by clustering characters whose x-gap is below
3px ('58,27' → ['58,27']; '58,27 152,70' → ['58,27', '152,70']).
"""

from __future__ import annotations

import io
import logging
import re
from collections import defaultdict
from datetime import date, datetime, timezone
from urllib.parse import urljoin

import pandas as pd
import pdfplumber

from core.http import make_session

logger = logging.getLogger(__name__)

_BASE = "https://www.osinergmin.gob.pe"
_LISTING_URL = (
    f"{_BASE}/seccion/institucional/Paginas/VisorPreciosReferencia.aspx?Codigo={{year}}"
)
_PDF_RE = re.compile(
    r"/seccion/centro_documental/gart/PreciosReferencia/"
    r"PrecioReferencia(\d{2})(\d{2})(\d{4})\.pdf",
    re.IGNORECASE,
)
_NUMBER_RE = re.compile(r"^\d{1,3}(?:,\d+)$")

_COUNTRY = "Peru"
_CURRENCY = "PEN"
_SOURCE_KEY = "pe_osinergmin_referencia_weekly"

# Column order in PR1 Soles/galón row (9 products).
_PR1_GALLON_PRODUCTS = (
    "GLP 70/30 gallon",  # also reported per-kg on the next row; we use per-kg
    "Gasolina Premium",
    "Gasolina Regular",
    "Gasolina 84",
    "Turbo",
    "Diesel B5 Bajo Azufre",
    "Diesel B5 Alto Azufre",
    "Petroleo Industrial 6",
    "Petroleo Industrial 500",
)
_PR1_SKIP_INDEXES = {0}  # skip GLP/gallon (replaced by per-kg below)

# Gasohol section (8 numbers): USD prefix then Soles, then alcohol pair.
# We only emit Soles values.
_GASOHOL_SOLES_INDEXES = {
    3: "Gasohol Premium",
    4: "Gasohol Regular",
    5: "Gasohol 84",
    7: "Alcohol Carburante",
}

# Diesel 2 + Biodiesel section (6 numbers): USD-pair, Soles-pair, USD bio, Soles bio.
_DIESEL2_SOLES_INDEXES = {
    2: "Diesel 2 Bajo Azufre",
    3: "Diesel 2 Alto Azufre",
    5: "Biodiesel B100",
}


def _parse_number(token: str) -> float | None:
    if not _NUMBER_RE.match(token):
        return None
    try:
        return float(token.replace(",", "."))
    except ValueError:
        return None


def _line_tokens(words: list[dict], gap_threshold: float = 3.0) -> list[str]:
    """Cluster a single-line list of pdfplumber 'words' into tokens by x-gap."""
    if not words:
        return []
    words = sorted(words, key=lambda w: w["x0"])
    tokens: list[str] = []
    cur = [words[0]["text"]]
    for prev, w in zip(words, words[1:]):
        if w["x0"] - prev["x1"] > gap_threshold:
            tokens.append("".join(cur))
            cur = [w["text"]]
        else:
            cur.append(w["text"])
    tokens.append("".join(cur))
    return tokens


def _extract_first_page_lines(pdf_bytes: bytes) -> list[list[str]]:
    """Reconstruct token rows from page 1, grouped by vertical position."""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        page = pdf.pages[0]
        words = page.extract_words()

    by_top: dict[int, list[dict]] = defaultdict(list)
    for w in words:
        key = round(w["top"] / 2) * 2
        by_top[key].append(w)

    return [_line_tokens(by_top[top]) for top in sorted(by_top.keys())]


def _extract_prices(pdf_bytes: bytes) -> dict[str, float]:
    """Return {product_name: price} for tracked products on a PR1 publication.

    Layout varies subtly between weeks: sometimes "Soles/galón" sits on the
    same y-row as its 9 prices, sometimes 2 pixels above. We handle both
    by tracking the most recently seen unit anchor and consuming the next
    numeric row of matching length.
    """
    out: dict[str, float] = {}
    rows = _extract_first_page_lines(pdf_bytes)

    pending_anchor: str | None = None  # 'soles_galon' | 'soles_kg' | None
    seen_pr1 = seen_glp_kg = seen_gasohol = seen_diesel2 = False

    for tokens in rows:
        if not tokens:
            continue
        numerics = [v for v in (_parse_number(t) for t in tokens) if v is not None]
        joined = " ".join(tokens)
        has_galon_anchor = "Soles/galón" in joined and not seen_pr1
        has_kg_anchor = "Soles/Kg" in joined and not seen_glp_kg

        # Case A: anchor and numerics share the row.
        if has_galon_anchor and len(numerics) == 9:
            for idx, value in enumerate(numerics):
                if idx in _PR1_SKIP_INDEXES:
                    continue
                out[_PR1_GALLON_PRODUCTS[idx]] = value
            seen_pr1 = True
            pending_anchor = None
            continue
        if has_kg_anchor and len(numerics) == 1:
            out["GLP 70/30"] = numerics[0]
            seen_glp_kg = True
            pending_anchor = None
            continue

        # Case B: anchor sits on its own row; remember and wait for next numeric row.
        if has_galon_anchor:
            pending_anchor = "soles_galon"
            continue
        if has_kg_anchor:
            pending_anchor = "soles_kg"
            continue

        # Skip rows that aren't purely numeric beyond this point.
        if not numerics or len(numerics) != len(tokens):
            continue

        if pending_anchor == "soles_galon" and len(numerics) == 9:
            for idx, value in enumerate(numerics):
                if idx in _PR1_SKIP_INDEXES:
                    continue
                out[_PR1_GALLON_PRODUCTS[idx]] = value
            seen_pr1 = True
            pending_anchor = None
            continue
        if pending_anchor == "soles_kg" and len(numerics) == 1:
            out["GLP 70/30"] = numerics[0]
            seen_glp_kg = True
            pending_anchor = None
            continue

        if seen_pr1 and not seen_gasohol and len(numerics) == 8:
            for idx, product in _GASOHOL_SOLES_INDEXES.items():
                out[product] = numerics[idx]
            seen_gasohol = True
            continue
        if seen_gasohol and not seen_diesel2 and len(numerics) == 6:
            for idx, product in _DIESEL2_SOLES_INDEXES.items():
                out[product] = numerics[idx]
            seen_diesel2 = True
            continue

    return out


def _list_year_pdfs(session, year: int) -> list[tuple[date, str]]:
    """Discover (publication_date, pdf_url) pairs for a given Codigo=YYYY page."""
    url = _LISTING_URL.format(year=year)
    try:
        resp = session.get(url, timeout=60)
        resp.raise_for_status()
    except Exception:
        logger.exception("[pe_osinergmin] Failed to load listing for %d", year)
        return []

    seen: set[str] = set()
    out: list[tuple[date, str]] = []
    for match in _PDF_RE.finditer(resp.text):
        path = match.group(0)
        if path in seen:
            continue
        seen.add(path)
        dd, mm, yyyy = int(match.group(1)), int(match.group(2)), int(match.group(3))
        try:
            pub_date = date(yyyy, mm, dd)
        except ValueError:
            continue
        out.append((pub_date, urljoin(_BASE, path)))
    return sorted(out, key=lambda t: t[0])


def fetch_pe_osinergmin_referencia(cutoff: date) -> pd.DataFrame | None:
    """Fetch Peru Osinergmin weekly PR1 reference prices (PEN/gallon; LPG in PEN/kg)."""
    today = datetime.now(timezone.utc).date()
    session = make_session()

    years = range(cutoff.year, today.year + 1)
    pdfs: list[tuple[date, str]] = []
    for year in years:
        pdfs.extend(_list_year_pdfs(session, year))

    pdfs = sorted({(d, u) for d, u in pdfs}, key=lambda t: t[0])
    if not pdfs:
        logger.warning("[pe_osinergmin] No PDFs discovered")
        return None

    rows: list[dict] = []
    for pub_date, url in pdfs:
        if pub_date <= cutoff:
            continue
        try:
            resp = session.get(url, timeout=90)
            resp.raise_for_status()
        except Exception:
            logger.exception("[pe_osinergmin] Failed to download %s", url)
            continue

        try:
            prices = _extract_prices(resp.content)
        except Exception:
            logger.exception("[pe_osinergmin] Failed to parse %s", url)
            continue

        if not prices:
            logger.warning("[pe_osinergmin] No prices parsed in %s", url)
            continue

        for product, price in prices.items():
            unit = "kg" if product == "GLP 70/30" else "gal"
            rows.append(
                {
                    "observation_date": pub_date.strftime("%Y-%m-%d"),
                    "country": _COUNTRY,
                    "fuel_product": product,
                    "price_local": round(price, 4),
                    "currency": _CURRENCY,
                    "source_key": _SOURCE_KEY,
                    "unit": unit,
                }
            )
        logger.info("[pe_osinergmin] %s → %d products", pub_date, len(prices))

    if not rows:
        logger.info("[pe_osinergmin] No new rows after cutoff %s", cutoff)
        return None

    out = (
        pd.DataFrame(rows)
        .sort_values(["observation_date", "fuel_product"])
        .reset_index(drop=True)
    )
    logger.info("[pe_osinergmin] Returning %d rows (cutoff: %s)", len(out), cutoff)
    return out
