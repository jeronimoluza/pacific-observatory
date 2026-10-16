"""CSPH Cameroon regulated retail pump prices (Douala), from the monthly PDFs.

CSPH publishes one scanned price-structure PDF per month. The Douala depot
page(s) (page 3, plus page 4 "via Limbé" since 2021) end with
'11 - Prix de gros à Douala TTC', '12 - Marge revendeur' and
'14 - Prix de détail TTC' rows for Super / Pétrole / Gasoil; English editions
carry the same rows as 'Douala wholesale price including taxes',
'Retailer margin' and 'Retail price including taxes'.

Discovery (all first-party, live on csph.cm):
  - since late 2025: dashboard/assets/uploads/pdfs/<Mois>_1_50.pdf (no year in
    the name; each month name is overwritten yearly, the year comes from the page)
  - 2016-2025: same folder, <MOIS>_<YYYY>.pdf / <Mois>_<YYYY>.pdf (French), with
    English <MONTH>_<YYYY>.pdf as fallback.
Wayback copies (images/publications/...) are capped at 1 MiB and unreadable,
so 2019 and late-2024 / mid-2025 months are gaps (filled by carry-forward).

The rows sit on grey shading, so pages are binarised and stripped of table
rules before OCR; each wanted row is then re-read on its own with a digit
whitelist. A product's price is kept only when two readings agree (row 14 on
two Douala pages, or row 14 against row 11 + row 12) and fall inside sanity
bounds, because OCR distorts the shaded Super column.
"""

from __future__ import annotations

import io
import logging
import re
import subprocess
import tempfile
import time
from collections import Counter
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageOps

from core.http import make_session
from fuel.fetchers.ssa.central_africa.cameroon.csph import (
    _EN_MONTH_NAMES,
    _FR_MONTH_NAMES,
    _LIVE_PDF_BASE,
    _MONTHS,
    _THROTTLE_S,
    _ascii,
    _download_pdf,
)

logger = logging.getLogger(__name__)

_SOURCE_KEY = "csph_cm_retail"
_COUNTRY = "Cameroon"
_CURRENCY = "XAF"
_CITY = "Douala"
_FIRST_YEAR = 2016
_DPI = 300
_INK = 110  # grey shading is ~185, ink ~60
_COLUMNS = ("Super", "Pétrole Lampant", "Gasoil")
# XAF/L. Retail has been 350 (kerosene) since 2016; Super/Gasoil 569-840.
_BOUNDS = {
    "Super": (450.0, 1300.0),
    "Gasoil": (400.0, 1300.0),
    "Pétrole Lampant": (200.0, 800.0),
}
_ROW_PATTERNS = {
    "retail": re.compile(r"d[ée]?tail\b.*\bTT|retail\s+price\s+incl", re.I),
    "wholesale": re.compile(r"gros.*TT|Douala\s*TT|wholesale\s+price\s+incl", re.I),
    "margin": re.compile(r"marge\s+rev|revendeur|retailer\s*margin", re.I),
}
_PRICE_RE = re.compile(r"(\d{1,4})[,.](\d{2})")
_PERIOD_RE = re.compile(
    r"(?:DU|FROM)\s+(\S{1,4})\s+(?:AU|TO)\s+\d{1,2}\s*(?:ST|ND|RD|TH)?\s+"
    r"([A-Za-zÉÛéû]+)\s+(20\d{2})",
    re.I,
)


# ── Discovery ────────────────────────────────────────────────────────────────


def _months(cutoff: date, today: date) -> list[date]:
    start = date(max(cutoff.year, _FIRST_YEAR), cutoff.month, 1)
    if cutoff.year < _FIRST_YEAR:
        start = date(_FIRST_YEAR, 1, 1)
    out, cur = [], start
    while cur <= today:
        out.append(cur)
        cur = date(cur.year + cur.month // 12, cur.month % 12 + 1, 1)
    return out


def _is_pdf(session, url: str) -> bool:
    """The upload folder honours Range, so a 8-byte read answers existence."""
    try:
        resp = session.get(url, headers={"Range": "bytes=0-7"}, timeout=(10, 30))
    except Exception:
        return False
    return resp.status_code in (200, 206) and resp.content[:4] == b"%PDF"


def _dated_names(month: date) -> list[str]:
    fr = _FR_MONTH_NAMES[month.month - 1]
    en = _EN_MONTH_NAMES[month.month - 1]
    names = (fr, fr.capitalize(), en.upper(), en)
    return [f"{n}_{month.year}.pdf" for n in names]


def _discover(session, cutoff: date, today: date) -> list[tuple[date, str]]:
    """(expected month, url) pairs, newest first."""
    found: dict[date, str] = {}
    for idx, fr in enumerate(_FR_MONTH_NAMES):
        month = idx + 1
        year = today.year if month <= today.month else today.year - 1
        expected = date(year, month, 1)
        if expected < cutoff.replace(day=1):
            continue
        url = f"{_LIVE_PDF_BASE}{fr.capitalize()}_1_50.pdf"
        if _is_pdf(session, url):
            found[expected] = url
    for month in _months(cutoff, today):
        if month in found:
            continue
        for name in _dated_names(month):
            url = f"{_LIVE_PDF_BASE}{name}"
            if _is_pdf(session, url):
                found[month] = url
                break
    logger.info("[csph_cm_retail] %d monthly PDFs discovered", len(found))
    return sorted(found.items(), reverse=True)


# ── OCR ──────────────────────────────────────────────────────────────────────


def _render(pdf_bytes: bytes, first: int, last: int) -> list[np.ndarray]:
    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = Path(tmp) / "in.pdf"
        pdf_path.write_bytes(pdf_bytes)
        cmd = ["pdftoppm", "-r", str(_DPI), "-gray", "-png"]
        cmd += ["-f", str(first), "-l", str(last), str(pdf_path), f"{tmp}/p"]
        subprocess.run(cmd, check=True, capture_output=True)
        return [
            np.array(Image.open(p).convert("L"))
            for p in sorted(Path(tmp).glob("p-*.png"))
        ]


def _deskew(gray: np.ndarray) -> np.ndarray:
    """Rotate so table rules are horizontal (scans are skewed up to ~2°)."""
    small = Image.fromarray(np.where(gray < _INK, 255, 0).astype(np.uint8))
    small = small.resize((small.width // 4, small.height // 4))
    best = max(
        np.arange(-3.0, 3.01, 0.1),
        key=lambda a: np.asarray(small.rotate(a)).sum(axis=1, dtype=float).var(),
    )
    if abs(best) < 0.05:
        return gray
    return np.asarray(Image.fromarray(gray).rotate(best, fillcolor=255))


def _erase_runs(img: np.ndarray, min_run: int, vertical: bool = False) -> np.ndarray:
    """Whiten straight ink runs longer than min_run (table rules, not glyphs)."""
    out = img.T.copy() if vertical else img.copy()
    for i, line in enumerate(out < 128):
        if not line.any():
            continue
        edges = np.flatnonzero(np.diff(np.r_[0, line.astype(np.int8), 0]))
        for start, end in zip(edges[::2], edges[1::2]):
            if end - start > min_run:
                out[i, start:end] = 255
    return out.T if vertical else out


def _strip_rules(gray: np.ndarray) -> np.ndarray:
    """Binarise (drops the grey row shading) and erase long table rules."""
    out = np.where(gray < _INK, 0, 255).astype(np.uint8)
    out = _erase_runs(out, out.shape[1] // 8)
    return _erase_runs(out, out.shape[0] // 30, vertical=True)


def _tesseract(img: Image.Image, psm: int, *extra: str) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    cmd = ["tesseract", "-", "-", "-l", "fra", "--psm", str(psm), *extra]
    res = subprocess.run(cmd, input=buf.getvalue(), capture_output=True)
    return res.stdout.decode("utf-8", "ignore")


def _gaps(rule: np.ndarray, min_width: int) -> list[tuple[int, int]]:
    """Runs of False in a boolean rule mask at least min_width long."""
    edges = np.flatnonzero(np.diff(np.r_[1, rule.astype(np.int8), 1]))
    return [(a, b) for a, b in zip(edges[::2], edges[1::2]) if b - a >= min_width]


def _ocr_box(img: np.ndarray, digits: bool = False) -> str:
    padded = ImageOps.expand(Image.fromarray(img), 20, fill=255)
    if digits:
        return _tesseract(padded, 7, "-c", "tessedit_char_whitelist=0123456789,.")
    return _tesseract(padded, 7)


def _read_cells(
    bw: np.ndarray, gray: np.ndarray, top: int, bottom: int
) -> list[list[float | None]]:
    """OCR each number cell (gaps between vertical rules) of one table row.

    Two readings: the binarised cell and the grey cell (tesseract's own
    thresholding keeps the thin, non-bold margin digits).
    """
    half = bw.shape[1] // 2
    # Rules run on through the row's top and bottom borders; a digit "1" does not.
    span = bw[max(0, top - 8) : bottom + 8, half:] < 128
    cells = _gaps(span.mean(axis=0) > 0.85, 60)
    cells = [(a, b) for a, b in cells if a > 0 and b < span.shape[1]][-3:]
    readings = []
    for img in (bw, gray):
        values: list[float | None] = []
        for left, right in cells:
            text = _ocr_box(img[top:bottom, half + left + 6 : half + right - 6], True)
            match = _PRICE_RE.search(text.replace(" ", ""))
            values.append(float(f"{match[1]}.{match[2]}") if match else None)
        readings.append(values)
    return readings


def _page_rows(gray: np.ndarray) -> tuple[str, dict[str, list[list[float | None]]]]:
    """(header text, {row kind: number readings}) for one rendered page.

    Table rows are the gaps between horizontal rules in the number columns;
    each row's label cell and number cells are OCR'd on their own, which
    survives the grey shading and the skew far better than page-level OCR.
    """
    gray = _deskew(gray)
    bw = np.where(gray < _INK, 0, 255).astype(np.uint8)
    clean = _strip_rules(bw)
    height, width = bw.shape
    header = _tesseract(Image.fromarray(clean[: height // 7]), 6)
    rules = (bw[:, width // 2 :] < 128).mean(axis=1) > 0.35
    rows: dict[str, list[list[float | None]]] = {}
    for top, bottom in _gaps(rules, 20):
        if top < height * 0.45 or bottom - top > 120:
            continue
        top, bottom = top + 3, bottom - 3
        label = _ocr_box(clean[top:bottom, : width // 2])
        if re.search(r"sortie|entr[ée]e|exit|\bHT\b|excl", label):
            continue
        for kind, pattern in _ROW_PATTERNS.items():
            if pattern.search(label):
                rows.setdefault(kind, []).extend(_read_cells(bw, gray, top, bottom))
                break
    return header, rows


# ── Extraction ───────────────────────────────────────────────────────────────


def _period(text: str) -> date | None:
    for match in _PERIOD_RE.finditer(text):
        month = _MONTHS.get(_ascii(match.group(2)).lower())
        if not month:
            continue
        first = match.group(1)
        day = int(first) if first.isdigit() and 1 <= int(first) <= 28 else 1
        return date(int(match.group(3)), month, day)
    return None


def _columns(values: list[float | None]) -> dict[str, float]:
    """The three number cells of a row are Super, Pétrole, Gasoil."""
    if len(values) != 3:
        return {}
    return {p: v for p, v in zip(_COLUMNS, values) if v is not None}


def _candidates(rows: dict[str, list[list[float | None]]]) -> dict[str, list[float]]:
    """One page's distinct values per product: row 14, and row 11 + row 12.

    Each method votes once per value, so two readings of the same cell
    never confirm each other.
    """
    direct: dict[str, set[float]] = {p: set() for p in _COLUMNS}
    derived: dict[str, set[float]] = {p: set() for p in _COLUMNS}
    for reading in rows.get("retail", []):
        for product, value in _columns(reading).items():
            direct[product].add(value)
    for gros_row in rows.get("wholesale", []):
        gros = _columns(gros_row)
        for marge_row in rows.get("margin", []):
            for product, marge in _columns(marge_row).items():
                if product in gros and 5 <= marge <= 60:
                    derived[product].add(round(gros[product] + marge, 2))
    return {p: [*direct[p], *derived[p]] for p in _COLUMNS}


def _vote(readings: list[float], product: str) -> float | None:
    """The value most votes agree on (at least two), in bounds and whole francs."""
    low, high = _BOUNDS[product]
    valid = [v for v in readings if low <= v <= high and v == int(v)]
    ranked = Counter(valid).most_common(2)
    if not ranked or ranked[0][1] < 2:
        return None
    if len(ranked) == 2 and ranked[1][1] == ranked[0][1]:
        return None
    return ranked[0][0]


def _extract(pdf_bytes: bytes) -> tuple[date | None, dict[str, float]]:
    readings: dict[str, list[float]] = {p: [] for p in _COLUMNS}
    period: date | None = None
    douala_pages = 0
    for first, last in ((3, 4), (1, 2), (5, 6)):
        try:
            pages = _render(pdf_bytes, first, last)
        except subprocess.CalledProcessError:
            continue
        for gray in pages:
            text, rows = _page_rows(gray)
            head = _ascii(text).upper()
            if "DOUALA" not in head or not rows or "LOCALITE" in head:
                continue
            douala_pages += 1
            period = period or _period(text)
            for product, values in _candidates(rows).items():
                readings[product].extend(values)
        if douala_pages:
            break
    prices = {}
    for product, values in readings.items():
        value = _vote(values, product)
        if value is None:
            logger.warning(
                "[csph_cm_retail] %s: no agreeing reading in %s", product, values
            )
        else:
            prices[product] = value
    return period, prices


def _row(obs_date: date, product: str, price: float) -> dict:
    return {
        "observation_date": obs_date.isoformat(),
        "country": _COUNTRY,
        "fuel_product": product,
        "price_local": price,
        "currency": _CURRENCY,
        "unit": "L",
        "source_key": _SOURCE_KEY,
        "city": _CITY,
    }


def fetch_csph_cm_retail(cutoff: date) -> pd.DataFrame | None:
    session = make_session()
    # csph.cm's TLS chain does not validate against the default CA bundle.
    session.verify = False
    today = date.today()
    rows: list[dict] = []
    seen: set[tuple[int, int]] = set()
    for expected, url in _discover(session, cutoff, today):
        time.sleep(_THROTTLE_S)
        pdf_bytes = _download_pdf(session, url)
        if not pdf_bytes:
            logger.warning("[csph_cm_retail] download failed: %s", url)
            continue
        period, prices = _extract(pdf_bytes)
        obs = period or expected
        if (obs.year, obs.month) in seen or obs < cutoff.replace(day=1):
            continue
        if period is None:
            logger.warning("[csph_cm_retail] no period on page; using %s", expected)
        seen.add((obs.year, obs.month))
        logger.info("[csph_cm_retail] %s -> %s %s", url.rsplit("/", 1)[-1], obs, prices)
        rows.extend(_row(obs, product, price) for product, price in prices.items())
    if not rows:
        logger.info("[csph_cm_retail] no rows after cutoff %s", cutoff)
        return None
    return (
        pd.DataFrame(rows)
        .sort_values(["observation_date", "fuel_product"])
        .reset_index(drop=True)
    )


__all__ = ["fetch_csph_cm_retail"]
