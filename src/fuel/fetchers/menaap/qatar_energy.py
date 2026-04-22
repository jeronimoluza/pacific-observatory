"""Qatar Energy monthly fuel prices fetcher (PDF-based).

Extraction strategy (2-phase):
  Phase 1: OCR page 1 image (tesseract --psm 3) for current month prices
  Phase 2: pdfplumber text extraction of page 2 history table

Source: https://www.qatarenergy.qa/en/Documents/Fuel%20Prices.pdf
  - Fixed URL, overwritten monthly
  - Page 1: infographic image with current month + 3 prices
  - Page 2: text table with ~11 months of history
"""

import io
import logging
import re
import shutil
import subprocess
import tempfile
from datetime import date
from pathlib import Path

import pandas as pd

from core.http import make_session

logger = logging.getLogger(__name__)

_PDF_URL = "https://www.qatarenergy.qa/en/Documents/Fuel%20Prices.pdf"

# Positional order of products on page 1 (left to right)
_PRODUCT_ORDER = ["Gasoline Premium", "Gasoline Super", "Diesel"]

# Month name variants found in the PDF (page 1 uses standard English,
# page 2 uses "Mars" for March and other minor variants)
_MONTH_MAP: dict[str, int] = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "mars": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

# Regex for page 2 table rows: "Month YYYY  price  price  price"
_TABLE_ROW_RE = re.compile(
    r"([A-Za-z]+)\s+(\d{4})\s+" r"(\d+\.\d{2})\s+" r"(\d+\.\d{2})\s+" r"(\d+\.\d{2})"
)

# Regex for page 1 OCR month: "APR 2026" or "APRIL 2026"
_PAGE1_MONTH_RE = re.compile(r"\b([A-Za-z]+)\s+(20\d{2})\b")

# Regex for page 1 OCR prices: three consecutive float values
_PAGE1_PRICES_RE = re.compile(r"(\d+\.\d{2})\s+(\d+\.\d{2})\s+(\d+\.\d{2})")

_TESSERACT_BIN = "/opt/homebrew/bin/tesseract"
if not Path(_TESSERACT_BIN).exists():
    _TESSERACT_BIN = shutil.which("tesseract") or ""

_META = {
    "country": "Qatar",
    "currency": "QAR",
    "source_key": "qe_qa_monthly",
    "unit": "L",
}


# ── PDF download ────────────────────────────────────────────────────


def _download_pdf(session) -> bytes | None:
    """Fetch the Qatar Energy fuel prices PDF."""
    try:
        resp = session.get(_PDF_URL, timeout=30)
        resp.raise_for_status()
        return resp.content
    except Exception:
        logger.exception("[qe_qa] Failed to download PDF from %s", _PDF_URL)
        return None


# ── Page 1: OCR extraction ──────────────────────────────────────────


def _parse_page1_ocr(pdf_bytes: bytes) -> list[dict]:
    """OCR page 1 and extract current month + 3 prices positionally."""
    if not _TESSERACT_BIN:
        logger.warning("[qe_qa] Tesseract not found — skipping page 1 OCR")
        return []

    try:
        import pdfplumber
    except ImportError:
        logger.warning("[qe_qa] pdfplumber not available — skipping page 1")
        return []

    tmp_dir = Path(tempfile.mkdtemp(prefix="qe_qa_"))
    try:
        img_path = tmp_dir / "page1.png"
        ocr_stem = tmp_dir / "page1_ocr"

        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            if len(pdf.pages) < 1:
                return []
            page = pdf.pages[0]
            page.to_image(resolution=300).save(str(img_path), format="PNG")

        result = subprocess.run(
            [_TESSERACT_BIN, str(img_path), str(ocr_stem), "-l", "eng", "--psm", "3"],
            capture_output=True,
            timeout=30,
            cwd=str(tmp_dir),
        )
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace")[:200]
            logger.warning("[qe_qa] Tesseract failed on page 1: %s", stderr)
            return []

        ocr_txt = Path(str(ocr_stem) + ".txt")
        if not ocr_txt.exists():
            return []
        ocr_text = ocr_txt.read_text(encoding="utf-8", errors="replace")

    except Exception:
        logger.exception("[qe_qa] Page 1 OCR failed")
        return []
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # Extract month/year
    obs_date = None
    for m in _PAGE1_MONTH_RE.finditer(ocr_text):
        month_str = m.group(1).lower()
        month_num = _MONTH_MAP.get(month_str)
        if month_num:
            year = int(m.group(2))
            obs_date = date(year, month_num, 1)
            break

    if obs_date is None:
        logger.warning("[qe_qa] Could not parse month from page 1 OCR")
        return []

    # Extract three prices
    prices_match = _PAGE1_PRICES_RE.search(ocr_text)
    if not prices_match:
        logger.warning("[qe_qa] Could not extract prices from page 1 OCR")
        return []

    prices = [float(prices_match.group(i)) for i in (1, 2, 3)]
    rows = []
    for product, price in zip(_PRODUCT_ORDER, prices):
        rows.append(
            {
                "observation_date": obs_date.strftime("%Y-%m-%d"),
                "country": _META["country"],
                "fuel_product": product,
                "price_local": price,
                "currency": _META["currency"],
                "source_key": _META["source_key"],
                "unit": _META["unit"],
            }
        )

    logger.info("[qe_qa] Page 1 OCR: %s → %d rows", obs_date, len(rows))
    return rows


# ── Page 2: text table extraction ───────────────────────────────────


def _parse_page2_text(pdf_bytes: bytes) -> list[dict]:
    """Parse the history table on page 2 using pdfplumber text extraction."""
    try:
        import pdfplumber
    except ImportError:
        logger.warning("[qe_qa] pdfplumber not available — skipping page 2")
        return []

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            if len(pdf.pages) < 2:
                logger.warning("[qe_qa] PDF has fewer than 2 pages")
                return []
            text = pdf.pages[1].extract_text() or ""
    except Exception:
        logger.exception("[qe_qa] Failed to extract text from page 2")
        return []

    rows = []
    for m in _TABLE_ROW_RE.finditer(text):
        month_str = m.group(1).lower()
        month_num = _MONTH_MAP.get(month_str)
        if month_num is None:
            logger.warning("[qe_qa] Unknown month name: %s", m.group(1))
            continue

        year = int(m.group(2))
        try:
            obs_date = date(year, month_num, 1)
        except ValueError:
            continue

        prices = [float(m.group(i)) for i in (3, 4, 5)]
        for product, price in zip(_PRODUCT_ORDER, prices):
            rows.append(
                {
                    "observation_date": obs_date.strftime("%Y-%m-%d"),
                    "country": _META["country"],
                    "fuel_product": product,
                    "price_local": price,
                    "currency": _META["currency"],
                    "source_key": _META["source_key"],
                    "unit": _META["unit"],
                }
            )

    logger.info("[qe_qa] Page 2 text: %d rows", len(rows))
    return rows


# ── Main fetcher ────────────────────────────────────────────────────


def fetch_qa_qatarenergy(cutoff: date) -> pd.DataFrame | None:
    """Fetch Qatar Energy monthly fuel prices from their official PDF."""
    session = make_session()
    pdf_bytes = _download_pdf(session)
    if pdf_bytes is None:
        return None

    # Parse both pages
    page1_rows = _parse_page1_ocr(pdf_bytes)
    page2_rows = _parse_page2_text(pdf_bytes)

    # Merge: page 1 takes precedence for overlapping months
    page1_dates = {r["observation_date"] for r in page1_rows}
    page2_unique = [r for r in page2_rows if r["observation_date"] not in page1_dates]
    all_rows = page1_rows + page2_unique

    if not all_rows:
        logger.info("[qe_qa] No rows extracted from PDF")
        return None

    # Filter by cutoff
    filtered = [
        r for r in all_rows if date.fromisoformat(r["observation_date"]) > cutoff
    ]

    if not filtered:
        logger.info("[qe_qa] No new rows after cutoff %s", cutoff)
        return None

    df = pd.DataFrame(filtered)
    df = df.sort_values("observation_date").reset_index(drop=True)
    logger.info("[qe_qa] Returning %d rows (cutoff: %s)", len(df), cutoff)
    return df
