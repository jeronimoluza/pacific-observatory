"""Guatemala MEM weekly fuel price fetcher.

Source: Ministerio de Energía y Minas, Dirección General de Hidrocarburos.
Index page:
  https://mem.gob.gt/que-hacemos/hidrocarburos/comercializacion-downstream/
  precios-combustible-nacionales/

MEM publishes a weekly "Informe Ejecutivo de Precios de los Combustibles"
PDF (Mon/Thu monitoring). The live index page is Cloudflare-protected for
plain HTTP, but the PDFs themselves at /wp-content/uploads/YYYY/MM/ are
directly downloadable. We discover PDF URLs by parsing Wayback snapshots
of the index page (sampled monthly) and download PDFs directly.

Each PDF embeds a 7-week comparison table under "COMPARACIÓN PRECIOS
PROMEDIO DE ÚLTIMAS SEMANAS" — one sample per ~6 weeks covers history.
Products tracked: Gasolina Superior, Gasolina Regular, Combustible Diesel
(autoservicio modality, GTQ/galón).
"""

from __future__ import annotations

import io
import logging
import re
import time
from datetime import date, datetime, timezone

import pandas as pd
import pdfplumber

from core.http import make_session

logger = logging.getLogger(__name__)

_INDEX_URL = (
    "https://mem.gob.gt/que-hacemos/hidrocarburos/"
    "comercializacion-downstream/precios-combustible-nacionales/"
)
_CDX_URL = (
    "https://web.archive.org/cdx/search/cdx?"
    "url={url}&from={frm}&output=json&filter=statuscode:200&filter=mimetype:text/html"
)
_WAYBACK_FMT = "https://web.archive.org/web/{ts}id_/{url}"
_PDF_HREF_RE = re.compile(
    r"https?://(?:web\.archive\.org/web/[^/]+/)?(?:www\.)?mem\.gob\.gt/"
    r"wp-content/uploads/\d{4}/\d{2}/[^\s\"'<>]*INFORME-EJECUTIVO[^\s\"'<>]*\.pdf",
    re.IGNORECASE,
)
_FILENAME_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})\.pdf", re.IGNORECASE)
_HEADER_RE = re.compile(
    r"COMPARACI[ÓO]N\s+PRECIOS\s+PROMEDIO\s+DE\s+[ÚU]LTIMAS\s+SEMANAS",
    re.IGNORECASE,
)
_PRODUCT_DATE_LINE_RE = re.compile(r"^Producto\b")
_DATE_TOKEN_RE = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{4})\b")
_PRICE_TOKEN_RE = re.compile(r"Q?\s?(-?\d+(?:\.\d+)?)")

_PRODUCTS = ("Gasolina Superior", "Gasolina Regular", "Combustible Diesel")
_COUNTRY = "Guatemala"
_CURRENCY = "GTQ"
_SOURCE_KEY = "gt_mem_weekly"
_FIRST_KNOWN = date(2024, 6, 1)
_REQUEST_DELAY_S = 1.5


def _direct_pdf_url(url: str) -> str:
    """Strip Wayback prefix so we can probe mem.gob.gt directly."""
    m = re.search(r"https?://(?:www\.)?mem\.gob\.gt/.*", url)
    return m.group(0) if m else url


def _list_snapshots(session, from_date: date) -> list[str]:
    """Return Wayback timestamps for index-page snapshots since from_date."""
    url = _CDX_URL.format(url=_INDEX_URL, frm=from_date.strftime("%Y%m%d"))
    try:
        resp = session.get(url, timeout=120)
        resp.raise_for_status()
        rows = resp.json()
    except Exception:
        logger.exception("[gt_mem] CDX query failed")
        return []
    if not rows or len(rows) <= 1:
        return []
    # First row is header [urlkey, timestamp, original, mimetype, statuscode, digest, length]
    return [row[1] for row in rows[1:] if row and len(row) >= 2]


def _discover_pdf_urls(session) -> list[str]:
    """Walk all Wayback snapshots of the index page, collect unique PDF URLs."""
    timestamps = _list_snapshots(session, _FIRST_KNOWN)
    if not timestamps:
        logger.warning("[gt_mem] No CDX snapshots returned")
        return []

    seen: set[str] = set()
    for ts in timestamps:
        snap_url = _WAYBACK_FMT.format(ts=ts, url=_INDEX_URL)
        try:
            resp = session.get(snap_url, timeout=45, allow_redirects=True)
        except Exception:
            time.sleep(_REQUEST_DELAY_S)
            continue
        if resp.status_code != 200:
            time.sleep(_REQUEST_DELAY_S)
            continue
        for match in _PDF_HREF_RE.findall(resp.text):
            seen.add(_direct_pdf_url(match))
        time.sleep(_REQUEST_DELAY_S)
    return sorted(seen)


def _pdf_date_from_filename(url: str) -> date | None:
    m = _FILENAME_DATE_RE.search(url)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _download_pdf(session, url: str) -> bytes | None:
    for attempt_url in (
        url,
        _WAYBACK_FMT.format(ts=datetime.now(timezone.utc).strftime("%Y%m%d"), url=url),
    ):
        try:
            resp = session.get(attempt_url, timeout=60)
            if resp.status_code == 200 and resp.headers.get(
                "Content-Type", ""
            ).startswith("application/pdf"):
                return resp.content
        except Exception:
            continue
    return None


def _parse_dates(line: str) -> list[date]:
    """Parse 'Producto DD/MM/YYYY ...' header row into date list."""
    dates: list[date] = []
    for tok in _DATE_TOKEN_RE.findall(line):
        try:
            dates.append(datetime.strptime(tok, "%d/%m/%Y").date())
        except ValueError:
            continue
    return dates


def _parse_prices(line: str, label: str, n: int) -> list[float] | None:
    """Parse '<label> Q39.48 Q39.48 ...' into a list of n floats."""
    tail = line[len(label) :].strip()
    nums: list[float] = []
    for tok in _PRICE_TOKEN_RE.findall(tail):
        try:
            nums.append(float(tok))
        except ValueError:
            continue
    if len(nums) < n:
        return None
    return nums[:n]


def _extract_observations(pdf_bytes: bytes) -> list[tuple[date, str, float]]:
    """Pull (date, product, price) triples from the 7-week comparison table."""
    out: list[tuple[date, str, float]] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text = pdf.pages[0].extract_text() or ""

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    # Find the "COMPARACIÓN ... ÚLTIMAS SEMANAS" header, then the "Producto" line.
    header_idx = next((i for i, ln in enumerate(lines) if _HEADER_RE.search(ln)), None)
    if header_idx is None:
        return out

    producto_idx = next(
        (
            i
            for i in range(header_idx + 1, min(header_idx + 6, len(lines)))
            if _PRODUCT_DATE_LINE_RE.match(lines[i])
        ),
        None,
    )
    if producto_idx is None:
        return out

    dates = _parse_dates(lines[producto_idx])
    if not dates:
        return out

    for product in _PRODUCTS:
        prod_line = next(
            (
                lines[i]
                for i in range(producto_idx + 1, min(producto_idx + 8, len(lines)))
                if lines[i].startswith(product)
            ),
            None,
        )
        if not prod_line:
            continue
        prices = _parse_prices(prod_line, product, len(dates))
        if not prices:
            continue
        for d, p in zip(dates, prices):
            if p > 0:
                out.append((d, product, p))
    return out


def fetch_gt_mem(cutoff: date) -> pd.DataFrame | None:
    """Fetch Guatemala MEM retail fuel prices (GTQ/gallon, autoservicio)."""
    session = make_session()
    pdf_urls = _discover_pdf_urls(session)
    if not pdf_urls:
        logger.warning("[gt_mem] No PDFs discovered from Wayback index snapshots")
        return None

    # Process PDFs sorted by date (oldest first); each gives 7 dates of history.
    pdf_urls_dated = sorted(
        ((_pdf_date_from_filename(u), u) for u in pdf_urls),
        key=lambda t: t[0] or date.min,
    )

    seen: set[tuple[date, str]] = set()
    rows: list[dict] = []

    for pdf_date, url in pdf_urls_dated:
        if pdf_date is None:
            continue
        # Skip PDFs whose latest date is at-or-before cutoff (no new data possible).
        if pdf_date <= cutoff:
            continue
        pdf_bytes = _download_pdf(session, url)
        time.sleep(_REQUEST_DELAY_S)
        if pdf_bytes is None:
            logger.warning("[gt_mem] Failed to download %s", url)
            continue
        for obs_date, product, price in _extract_observations(pdf_bytes):
            if obs_date <= cutoff:
                continue
            key = (obs_date, product)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "observation_date": obs_date.strftime("%Y-%m-%d"),
                    "country": _COUNTRY,
                    "fuel_product": product,
                    "price_local": round(price, 4),
                    "currency": _CURRENCY,
                    "source_key": _SOURCE_KEY,
                    "unit": "gal",
                }
            )
        logger.info(
            "[gt_mem] %s → %d rows so far (cumulative)",
            pdf_date,
            len(rows),
        )

    if not rows:
        logger.info("[gt_mem] No new rows after cutoff %s", cutoff)
        return None

    out = (
        pd.DataFrame(rows)
        .sort_values(["observation_date", "fuel_product"])
        .reset_index(drop=True)
    )
    logger.info("[gt_mem] Returning %d rows (cutoff: %s)", len(out), cutoff)
    return out
