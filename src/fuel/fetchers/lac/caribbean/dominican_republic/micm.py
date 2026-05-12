"""Dominican Republic MICM weekly fuel price fetcher.

Source: https://micm.gob.do/direcciones/combustibles/avisos-semanales-de-precios/
        avisos-semanales-de-precios-de-combustibles/

The Ministerio de Industria, Comercio y MiPymes publishes a weekly
"Aviso Oficial" PDF setting retail prices for the Saturday→Friday window.
Each PDF is uploaded to /wp-content/uploads/{YYYY}/{MM}/AVISO-PRE.-SEM.CORTE-
{D1}-{D2}-{MMM}-DE-{YYYY}-.pdf.

The category page lists only the 3-5 most recent PDFs (older avisos live
in a JS-rendered "Histórico" view that we cannot reach via plain HTTP),
so this fetcher pulls the visible head of the archive and relies on
weekly cadence + carry_forward to keep the local store fresh.

Products extracted from each PDF (PRECIO OFICIAL A PAGAR POR EL PUBLICO,
RD$/gallon — second-to-last numeric token on each product row):
  Gasolina Premium / Regular, Gasoil Regular / Optimo, Avtur, Kerosene,
  Fuel Oil, Gas Licuado de Petróleo (GLP).
"""

from __future__ import annotations

import io
import logging
import re
import unicodedata
from datetime import date

import pandas as pd
import pdfplumber

from core.http import make_session

logger = logging.getLogger(__name__)

_LISTING_URL = (
    "https://micm.gob.do/direcciones/combustibles/avisos-semanales-de-precios/"
    "avisos-semanales-de-precios-de-combustibles/"
)
_PDF_URL_RE = re.compile(
    r"https://micm\.gob\.do/wp-content/uploads/(\d{4})/(\d{2})/"
    r"(AVISO-PRE[^\s\"']+\.pdf)",
    re.IGNORECASE,
)
_DAY_RE = re.compile(r"CORTE-(\d{1,2})", re.IGNORECASE)

_COUNTRY = "Dominican Republic"
_CURRENCY = "DOP"
_SOURCE_KEY = "do_micm_weekly"

# Order matters: longer product names first so "Gasoil Optimo" wins over
# "Gasoil" prefix, and we skip industrial subsidy variants ("EGP-C", "1% Azufre").
_PRODUCT_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("Gasolina Premium", re.compile(r"^gasolina\s+premium\s*$", re.IGNORECASE)),
    ("Gasolina Regular", re.compile(r"^gasolina\s+regular\s*$", re.IGNORECASE)),
    ("Gasoil Optimo", re.compile(r"^gasoil\s+optimo\s*$", re.IGNORECASE)),
    ("Gasoil Regular", re.compile(r"^gasoil\s+regular\s*$", re.IGNORECASE)),
    ("Avtur", re.compile(r"^avtur\s*$", re.IGNORECASE)),
    ("Kerosene", re.compile(r"^kerosene\s*$", re.IGNORECASE)),
    ("Fuel Oil", re.compile(r"^fuel\s+oil\s*$", re.IGNORECASE)),
    ("GLP", re.compile(r"^gas\s+licuado\s+de\s+petr.*?\(glp\)", re.IGNORECASE)),
]

_NUMBER_RE = re.compile(r"\(?-?\d{1,3}(?:,\d{3})*(?:\.\d+)?\)?")


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"\s+", " ", text).strip()


def _list_pdfs(session) -> list[tuple[date, str]]:
    """Return [(start_date, pdf_url), ...] for PDFs visible on the listing page."""
    try:
        resp = session.get(_LISTING_URL, timeout=60)
        resp.raise_for_status()
    except Exception:
        logger.exception("[do_micm] Failed to fetch avisos listing")
        return []

    seen: set[str] = set()
    out: list[tuple[date, str]] = []
    for match in _PDF_URL_RE.finditer(resp.text):
        year, month, filename = int(match.group(1)), int(match.group(2)), match.group(3)
        url = match.group(0)
        if url in seen:
            continue
        seen.add(url)
        day_match = _DAY_RE.search(filename)
        if not day_match:
            continue
        try:
            start = date(year, month, int(day_match.group(1)))
        except ValueError:
            continue
        out.append((start, url))
    return sorted(out, key=lambda t: t[0])


def _parse_number(token: str) -> float | None:
    # PDFs show negative values as "(4.10)" parentheses notation.
    text = token.strip()
    neg = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    text = text.replace(",", "")
    if not text:
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    return -value if neg else value


def _match_product(line: str) -> str | None:
    """Return canonical product name if the line begins with a tracked product."""
    # Strip the product name from the head (before the first run of numbers).
    head = _NUMBER_RE.split(line, maxsplit=1)[0]
    head = _normalize(head).rstrip("*").rstrip()
    for canonical, pattern in _PRODUCT_PATTERNS:
        if pattern.match(head):
            return canonical
    return None


def _extract_prices(pdf_bytes: bytes) -> dict[str, float]:
    """Pull PRECIO OFICIAL A PAGAR POR EL PUBLICO for each tracked product."""
    out: dict[str, float] = {}
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for raw_line in text.splitlines():
                line = _normalize(raw_line)
                if not line:
                    continue
                product = _match_product(line)
                if product is None or product in out:
                    continue
                tokens = _NUMBER_RE.findall(line)
                values = [
                    v for v in (_parse_number(t) for t in tokens) if v is not None
                ]
                if len(values) < 2:
                    continue
                # Second-to-last = "PRECIO OFICIAL A PAGAR POR EL PUBLICO".
                public_price = values[-2]
                if public_price <= 0:
                    continue
                out[product] = public_price
    return out


def fetch_do_micm(cutoff: date) -> pd.DataFrame | None:
    """Fetch Dominican Republic MICM weekly retail fuel prices (DOP/gallon)."""
    session = make_session()
    pdfs = _list_pdfs(session)
    if not pdfs:
        logger.warning("[do_micm] No avisos visible on listing page")
        return None

    rows: list[dict] = []
    for start, url in pdfs:
        if start <= cutoff:
            continue
        try:
            resp = session.get(url, timeout=60)
            resp.raise_for_status()
        except Exception:
            logger.exception("[do_micm] Failed to download %s", url)
            continue

        prices = _extract_prices(resp.content)
        if not prices:
            logger.warning("[do_micm] No prices parsed from %s", url)
            continue

        for product, price in prices.items():
            rows.append(
                {
                    "observation_date": start.strftime("%Y-%m-%d"),
                    "country": _COUNTRY,
                    "fuel_product": product,
                    "price_local": round(price, 4),
                    "currency": _CURRENCY,
                    "source_key": _SOURCE_KEY,
                    "unit": "gal",
                }
            )
        logger.info("[do_micm] %s → %d products", start, len(prices))

    if not rows:
        logger.info("[do_micm] No new rows after cutoff %s", cutoff)
        return None

    out = (
        pd.DataFrame(rows)
        .sort_values(["observation_date", "fuel_product"])
        .reset_index(drop=True)
    )
    logger.info("[do_micm] Returning %d rows (cutoff: %s)", len(out), cutoff)
    return out
