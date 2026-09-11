"""Shared OCR fallback for fetchers whose source publishes scanned PDFs.

A number of official price/tariff publishers in the gap countries gazette
their schedules as image-only PDFs -- a photocopy or phone scan of a signed
paper Order, wrapped in a PDF container with no text layer at all. Before
this module those documents were detected (``pdfplumber`` returns nothing)
and skipped with a warning, which is why e.g. Kiribati's MCIC price-control
series stopped at 2022-06-14 even though a 2024 Order is published.

The path here is deliberately dependency-free: it shells out to
``pdftoppm`` (poppler) and ``tesseract``, both already installed on the
collection host. ``ocrmypdf``/``pytesseract``/``pdf2image``/``fitz`` are NOT
used and are not project dependencies. ``ocr_available()`` reports whether
the two binaries are on PATH; every caller must treat OCR as optional and
degrade to its existing "skip and log" behaviour when it is not.

WHY A RULED-GRID PARSER RATHER THAN OCR LINE TEXT
--------------------------------------------------
Reading tesseract's line text and splitting on whitespace is the obvious
approach and it is unsafe for price tables: when OCR drops a single cell
(common on faint scans) every later number on that line shifts one column
left, so a per-kg figure is silently emitted as a retail price. That is
indistinguishable from a real price downstream.

So instead the page is parsed the way the document is actually drawn. These
are ruled tables; the rules survive scanning far better than the glyphs do.
``page_grid()``:

  1. renders the page at 300 dpi (``pdftoppm``),
  2. asks tesseract's OSD (``--psm 0``) for the page orientation -- scans of
     landscape schedules are routinely dropped into a portrait PDF page, and
     the orientation varies *within* one document,
  3. finds the table's vertical and horizontal rules as long runs of ink in
     the column/row ink profile of the uprighted image,
  4. OCRs the page and places every word in a (row, column) cell by the
     centre of its own bounding box.

A cell that OCR could not read stays ``None`` instead of pulling its
neighbour's value across. The output is the same ``list[list[str | None]]``
shape ``pdfplumber``'s ``extract_tables()`` returns, so a fetcher can feed
an OCR'd scan through the table parser it already has.

The page is OCR'd in its ORIGINAL orientation rather than pre-rotated:
tesseract's own per-block orientation handling reads these scans measurably
more accurately than feeding it an image rotated by PIL (measured on
Kiribati's 2024 Order: pre-rotating turned "28.50 31.65 34.25 37.70" into
"8850 81.65 84.25 87.70"). Word boxes are therefore transposed into the
uprighted frame afterwards so that they share a coordinate system with the
detected rules.

OCR TEXT IS NOT TRUSTED
-----------------------
``money()`` is intentionally strict. Every price in these gazettes is
written with exactly two decimals, so a cell is accepted only if it reads as
``<digits>.<2 digits>`` after a small, closed set of separator repairs
(``,`` ``:`` ``;`` -> ``.``), sits inside a caller-supplied plausible range,
and carries an OCR confidence at or above ``min_conf``. Anything else --
``245`` for ``2.45``, ``1-25``, ``2315`` -- is rejected rather than guessed
at, and the caller is handed the reject count so it can report it. A missing
row is recoverable later; a wrong price is not.

CACHING
-------
OCR is slow (roughly 1-4s per page on top of the render). Every document's
parsed grid is cached under ``data/_ocr_cache/<sha1-of-pdf-bytes>-<dpi>.json``
and keyed by the PDF's own bytes, so re-running a fetcher never re-OCRs a
document it has already read, and a republished PDF (different bytes) is
correctly treated as new work.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import re
import shutil
import statistics
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_DPI = 300
# Below this the glyphs on a 300-dpi phone scan are usually mis-shaped enough
# that the "two decimals" test starts passing on wrong digits.
DEFAULT_MIN_CONF = 55.0

_CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "_ocr_cache"

# A CONTIGUOUS run of ink this fraction of the page long is a rule, not a glyph.
_RULE_SPAN = 0.30
# At 300 dpi a drawn rule is ~5-9 px thick; 1-4 px runs are stacked text.
_RULE_MIN_THICKNESS = 5
_RULE_MERGE_GAP = 4

_MONEY_RE = re.compile(r"^(\d{1,6})\.(\d{2})$")
# Separators tesseract routinely substitutes for a decimal point. Deliberately
# does NOT include "-" or " ": "1-25" and "1 25" are ambiguous enough that
# repairing them would invent a price.
_SEP_FIX = str.maketrans({",": ".", ":": ".", ";": "."})
_STRIP = " \t|[]{}()_'\"`$"


def ocr_available() -> bool:
    """True when both binaries this module shells out to are on PATH."""
    return bool(shutil.which("pdftoppm") and shutil.which("tesseract"))


def pdf_text_chars(content: bytes) -> int:
    """Non-whitespace characters in the PDF's text layer, across all pages."""
    import pdfplumber

    total = 0
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                total += len(re.sub(r"\s+", "", page.extract_text() or ""))
    except Exception:
        logger.debug("pdf_text_chars failed", exc_info=True)
        return 0
    return total


def is_scanned(content: bytes, min_chars: int = 100) -> bool:
    """True when the PDF carries no usable text layer, i.e. it is an image."""
    return pdf_text_chars(content) < min_chars


def money(
    text: str | None,
    *,
    lo: float,
    hi: float,
    conf: float | None = None,
    min_conf: float = DEFAULT_MIN_CONF,
) -> float | None:
    """Parse an OCR'd price cell, or return None. Never guesses.

    Accepts only ``<digits>.<exactly two digits>`` after repairing the closed
    set of separators tesseract substitutes for a decimal point, and only
    inside [lo, hi]. ``conf`` is tesseract's own per-word confidence when the
    caller has it.
    """
    if text is None:
        return None
    if conf is not None and conf < min_conf:
        return None
    raw = str(text).strip(_STRIP).translate(_SEP_FIX)
    # Some cells publish a per-carton/per-unit pair as "15.25/2.50"; the
    # leading figure is the one that belongs to the column.
    raw = raw.split("/", 1)[0].strip(_STRIP)
    m = _MONEY_RE.match(raw)
    if not m:
        return None
    value = float(raw)
    if value < lo or value > hi:
        return None
    return value


_ALPHA_RE = re.compile(r"[A-Za-z]")


def looks_like_item_name(text: str | None, *, min_alpha_ratio: float = 0.45) -> bool:
    """Reject OCR garbage in a product-name cell.

    A real item name is mostly letters. A cell that is mostly punctuation and
    stray rule fragments ("|__al", "Sa,", "=e") is OCR noise and must not be
    emitted as a product.
    """
    if not text:
        return False
    s = str(text).strip()
    if len(s.replace(" ", "")) < 3:
        return False
    body = s.replace(" ", "")
    alpha = len(_ALPHA_RE.findall(body))
    return alpha / len(body) >= min_alpha_ratio


@dataclass(frozen=True)
class OcrWord:
    text: str
    x: int
    y: int
    w: int
    h: int
    conf: float

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2


@dataclass
class OcrPage:
    number: int
    width: int
    height: int
    rotate: int
    words: list[OcrWord]
    col_rules: list[int]
    row_rules: list[int]


def _reading_rotation(words: list[dict]) -> int:
    """Page rotation measured from the OCR word boxes themselves.

    Tesseract's OSD (``--psm 0``) is the obvious source and it is not reliable
    enough here: on Kiribati's 2024 Order it reported 90 for a page whose text
    actually runs the other way, which mirrors the whole table and puts the
    product column on the right. The word boxes are unambiguous, so the
    direction is measured instead of asked for -- within one recognised line,
    successive words advance along the reading axis, and the sign of that
    advance is the rotation.
    """
    seq: dict[tuple, list[dict]] = {}
    for d in words:
        seq.setdefault((d["block"], d["par"], d["line"]), []).append(d)
    dl = dt = 0
    for grp in seq.values():
        if len(grp) < 2:
            continue
        grp.sort(key=lambda d: d["word"])
        for a, b in zip(grp, grp[1:]):
            dl += b["l"] - a["l"]
            dt += b["t"] - a["t"]
    if abs(dl) >= abs(dt):
        return 0 if dl >= 0 else 180
    return 270 if dt > 0 else 90


def _tsv_words(png: str) -> list[dict]:
    import csv

    try:
        r = subprocess.run(
            ["tesseract", png, "stdout", "tsv"],
            capture_output=True,
            text=True,
            timeout=600,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    out: list[dict] = []
    reader = csv.DictReader(
        io.StringIO(r.stdout), delimiter="\t", quoting=csv.QUOTE_NONE
    )
    for d in reader:
        if d.get("level") != "5":
            continue
        text = (d.get("text") or "").strip()
        if not text:
            continue
        try:
            out.append(
                {
                    "l": int(d["left"]),
                    "t": int(d["top"]),
                    "w": int(d["width"]),
                    "h": int(d["height"]),
                    "conf": float(d["conf"]),
                    "text": text,
                    "block": int(d["block_num"]),
                    "par": int(d["par_num"]),
                    "line": int(d["line_num"]),
                    "word": int(d["word_num"]),
                }
            )
        except (TypeError, ValueError, KeyError):
            continue
    return out


def _upright(d: dict, rot: int, src_w: int, src_h: int) -> OcrWord:
    """Map a word box from the page's own frame into the uprighted frame.

    Matches PIL's ``Image.rotate(-rot, expand=True)``, which is what the rule
    detector sees.
    """
    l, t, w, h = d["l"], d["t"], d["w"], d["h"]
    if rot == 270:
        x, y, ww, hh = t, src_w - l - w, h, w
    elif rot == 90:
        x, y, ww, hh = src_h - t - h, l, h, w
    elif rot == 180:
        x, y, ww, hh = src_w - l - w, src_h - t - h, w, h
    else:
        x, y, ww, hh = l, t, w, h
    return OcrWord(text=d["text"], x=x, y=y, w=ww, h=hh, conf=d["conf"])


def _runs(idx, gap: int) -> list[tuple[int, int]]:
    runs: list[list[int]] = []
    for i in idx:
        i = int(i)
        if runs and i - runs[-1][1] <= gap:
            runs[-1][1] = i
        else:
            runs.append([i, i])
    return [(a, b) for a, b in runs]


def _longest_run(ink, axis: int, close: int = 2):
    """Longest contiguous run of ink along ``axis``, per row/column.

    Total ink in a line is NOT a usable rule test: a column of right-aligned
    prices stacks enough glyph ink to beat any sum threshold. A drawn rule is
    distinguished by being CONTINUOUS over most of the table, so the run
    length is what gets measured. Gaps up to ``close`` px are bridged first --
    scanned rules are speckled.
    """
    import numpy as np

    a = ink if axis == 0 else ink.T
    if close:
        closed = a.copy()
        for k in range(1, close + 1):
            closed |= np.roll(a, k, axis=0)
            closed |= np.roll(a, -k, axis=0)
        a = closed
    run = np.zeros(a.shape[1], dtype=np.int32)
    best = np.zeros(a.shape[1], dtype=np.int32)
    for i in range(a.shape[0]):
        run = (run + 1) * a[i]
        np.maximum(best, run, out=best)
    return best


def _rules(profile, span_limit: int) -> list[int]:
    import numpy as np

    hits = np.where(profile > span_limit)[0]
    out = []
    for a, b in _runs(hits, _RULE_MERGE_GAP):
        if b - a + 1 >= _RULE_MIN_THICKNESS:
            out.append((a + b) // 2)
    return out


def _page_from_png(png: str, number: int) -> OcrPage:
    import numpy as np
    from PIL import Image

    tsv = _tsv_words(png)
    rot = _reading_rotation(tsv)
    raw = Image.open(png).convert("L")
    src_w, src_h = raw.size
    img = raw.rotate(-rot, expand=True) if rot else raw
    arr = np.asarray(img)
    height, width = arr.shape
    ink = arr < 160
    col_rules = _rules(_longest_run(ink, 0), int(_RULE_SPAN * height))
    row_rules = _rules(_longest_run(ink, 1), int(_RULE_SPAN * width))
    words = [_upright(d, rot, src_w, src_h) for d in tsv]
    return OcrPage(
        number=number,
        width=width,
        height=height,
        rotate=rot,
        words=words,
        col_rules=col_rules,
        row_rules=row_rules,
    )


def ocr_pages(
    content: bytes,
    *,
    dpi: int = DEFAULT_DPI,
    first: int | None = None,
    last: int | None = None,
) -> list[OcrPage]:
    """Render and OCR a PDF. Uncached -- callers normally want ``page_grids``."""
    if not ocr_available():
        raise RuntimeError("OCR requested but pdftoppm/tesseract are not on PATH")
    pages: list[OcrPage] = []
    with tempfile.TemporaryDirectory(prefix="prices-ocr-") as tmp:
        pdf_path = os.path.join(tmp, "in.pdf")
        with open(pdf_path, "wb") as fh:
            fh.write(content)
        cmd = ["pdftoppm", "-r", str(dpi), "-png"]
        if first is not None:
            cmd += ["-f", str(first)]
        if last is not None:
            cmd += ["-l", str(last)]
        cmd += [pdf_path, os.path.join(tmp, "pg")]
        subprocess.run(cmd, check=True, capture_output=True, timeout=1800)
        names = sorted(n for n in os.listdir(tmp) if n.endswith(".png"))
        for i, name in enumerate(names, start=first or 1):
            pages.append(_page_from_png(os.path.join(tmp, name), i))
    return pages


def grid_of(
    page: OcrPage, *, min_cols: int = 2, min_conf: float = DEFAULT_MIN_CONF
) -> list[list[str | None]]:
    """Lay a page's OCR words onto the cell grid its own ruled lines define.

    Rows come from the detected horizontal rules when the page has enough of
    them, and from clustering word baselines otherwise (some scans lose the
    horizontal rules but keep the verticals). Columns always come from the
    vertical rules: guessing column boundaries from where the numbers happen
    to sit is what shifts a per-kg figure into the retail column.

    Words tesseract read with confidence below ``min_conf`` are dropped here
    rather than downstream, so a doubtful glyph leaves its cell EMPTY. That is
    the safe failure: an empty cell loses a row, a kept one can invent a price.
    """
    cols = page.col_rules
    if len(cols) < min_cols + 1:
        return []
    bounds = list(zip(cols[:-1], cols[1:]))
    keep = [w for w in page.words if w.conf >= min_conf]

    rows = page.row_rules
    if len(rows) >= 4:
        row_bounds = list(zip(rows[:-1], rows[1:]))

        def row_index(w: OcrWord) -> int | None:
            for i, (a, b) in enumerate(row_bounds):
                if a <= w.cy < b:
                    return i
            return None

        buckets: dict[int, list[OcrWord]] = {}
        for w in keep:
            i = row_index(w)
            if i is None:
                continue
            buckets.setdefault(i, []).append(w)
        ordered = [buckets[i] for i in sorted(buckets)]
    else:
        ordered = [grp for _, grp in group_lines(keep)]

    out: list[list[str | None]] = []
    for group in ordered:
        cells: list[list[str]] = [[] for _ in bounds]
        for w in sorted(group, key=lambda z: z.cx):
            for i, (a, b) in enumerate(bounds):
                if a <= w.cx < b:
                    cells[i].append(w.text)
                    break
        row = [" ".join(c).strip() or None for c in cells]
        if any(row):
            out.append(row)
    return out


def group_lines(words: list[OcrWord], *, tol_ratio: float = 0.55):
    """Cluster words into visual lines by the centre of their bounding box."""
    if not words:
        return []
    med = statistics.median(w.h for w in words)
    tol = max(8.0, med * tol_ratio)
    ordered = sorted(words, key=lambda w: w.cy)
    out: list[list] = []
    for w in ordered:
        if out and abs(w.cy - out[-1][0]) <= tol:
            n = len(out[-1][1])
            out[-1][0] = (out[-1][0] * n + w.cy) / (n + 1)
            out[-1][1].append(w)
        else:
            out.append([w.cy, [w]])
    for _, grp in out:
        grp.sort(key=lambda w: w.x)
    return [(yc, grp) for yc, grp in out]


def page_grids(
    content: bytes,
    *,
    dpi: int = DEFAULT_DPI,
    min_conf: float = DEFAULT_MIN_CONF,
    cache: bool = True,
    cache_dir: Path | None = None,
) -> list[list[list[str | None]]]:
    """One ruled-cell grid per page, cached on the PDF's own bytes.

    Returns ``[]`` when OCR is unavailable so a caller can fall back to its
    pre-OCR behaviour without special-casing the import.
    """
    if not ocr_available():
        logger.warning("OCR unavailable (need pdftoppm + tesseract on PATH)")
        return []
    root = cache_dir or _CACHE_DIR
    key = hashlib.sha1(content).hexdigest()
    path = root / f"{key}-{dpi}-{int(min_conf)}.json"
    if cache and path.exists():
        try:
            return json.loads(path.read_text())
        except (OSError, ValueError):
            logger.debug("discarding unreadable OCR cache %s", path)
    grids = [grid_of(p, min_conf=min_conf) for p in ocr_pages(content, dpi=dpi)]
    if cache:
        try:
            root.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(grids))
        except OSError:
            logger.debug("could not write OCR cache %s", path, exc_info=True)
    return grids
