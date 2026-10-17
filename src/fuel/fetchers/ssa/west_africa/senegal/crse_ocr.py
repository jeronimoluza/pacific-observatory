"""Page-3 table reader for the CRSE Senegal price structures (OCR).

Shells out to tesseract (French data) on images rendered by pdftoppm; see
crse.py for the reading rules. Kept apart from crse.py for the 500-line cap.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
import unicodedata
from pathlib import Path

import numpy as np
from PIL import Image

PRODUCTS = (
    "Super",
    "Essence ordinaire",
    "Essence pirogue",
    "Pétrole lampant",
    "Gasoil",
)
_HEADERS = ("SUPER", "ORDINAIRE", "PIROGUE", "LAMPANT", "GASOIL")
_MIN_XOF, _MAX_XOF = 300, 2000


def ascii_lower(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def _tesseract(image: Image.Image, *args: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "p.png"
        image.save(path)
        proc = subprocess.run(
            ["tesseract", str(path), "stdout", *args],
            capture_output=True,
            text=True,
            check=False,
        )
        return proc.stdout


def render_page3(pdf_bytes: bytes, dpi: int) -> Image.Image:
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "in.pdf"
        pdf.write_bytes(pdf_bytes)
        subprocess.run(
            [
                "pdftoppm",
                "-r",
                str(dpi),
                "-png",
                "-f",
                "3",
                "-l",
                "3",
                "-singlefile",
                str(pdf),
                str(Path(tmp) / "p3"),
            ],
            check=True,
            capture_output=True,
        )
        img = Image.open(Path(tmp) / "p3.png")
        img.load()
        return img


def _words(image: Image.Image) -> list[dict]:
    tsv = _tesseract(image, "-l", "fra", "--psm", "6", "tsv")
    words = []
    for line in tsv.splitlines()[1:]:
        f = line.split("\t")
        if len(f) == 12 and f[11].strip():
            words.append(
                {
                    "line": (int(f[2]), int(f[3]), int(f[4])),
                    "x": int(f[6]),
                    "y": int(f[7]),
                    "w": int(f[8]),
                    "h": int(f[9]),
                    "text": f[11],
                }
            )
    return words


def _lines(words: list[dict]) -> list[list[dict]]:
    by_line: dict[tuple, list[dict]] = {}
    for w in words:
        by_line.setdefault(w["line"], []).append(w)
    return list(by_line.values())


def _per_litre(digits: str) -> int | None:
    """XOF/L from one cell's digits: 6-7 digits are F CFA/m3, 3-4 are F CFA/L."""
    if len(digits) in (6, 7):
        return round(int(digits) / 1000)
    if len(digits) in (3, 4):
        return int(digits)
    return None


def deskew(image: Image.Image) -> Image.Image:
    """Undo a small scan tilt: the angle that makes text rows sharpest."""
    gray = image.convert("L")
    small = gray.resize((gray.width // 3, gray.height // 3))
    angles = np.arange(-3.0, 3.01, 0.1)
    scores = [
        (np.asarray(small.rotate(a, fillcolor=255)) < 128).sum(axis=1).var()
        for a in angles
    ]
    best = float(angles[int(np.argmax(scores))])
    if abs(best) < 0.05:
        return gray
    return gray.rotate(best, resample=Image.BICUBIC, fillcolor=255)


def _columns(words: list[dict], above_y: int) -> list[float] | None:
    """x centre of each product column from the header row, gaps interpolated."""
    found: dict[int, float] = {}
    for w in words:
        token = re.sub(r"[^A-Z]", "", ascii_lower(w["text"]).upper())
        for i, head in enumerate(_HEADERS):
            if token == head and w["y"] < above_y and i not in found:
                found[i] = w["x"] + w["w"] / 2
    if len(found) < 3:
        return _columns_from_rows(words, above_y)
    idx = sorted(found)
    step = (found[idx[-1]] - found[idx[0]]) / (idx[-1] - idx[0])
    if step <= 0:
        return None
    return [found.get(i, found[idx[0]] + (i - idx[0]) * step) for i in range(5)]


def _columns_from_rows(words: list[dict], above_y: int) -> list[float] | None:
    """Column centres from table rows above the price row that split into 5 cells."""
    centres = []
    for line in _lines([w for w in words if w["y"] < above_y]):
        nums = sorted(
            (w for w in line if len(re.sub(r"\D", "", w["text"])) >= 2),
            key=lambda w: w["x"],
        )
        if len(nums) < 5:
            continue
        gap = 1.5 * sorted(w["h"] for w in nums)[len(nums) // 2]
        groups = [[nums[0]]]
        for prev, w in zip(nums, nums[1:]):
            if w["x"] - (prev["x"] + prev["w"]) > gap:
                groups.append([])
            groups[-1].append(w)
        if len(groups) == 5:
            centres.append([(g[0]["x"] + g[-1]["x"] + g[-1]["w"]) / 2 for g in groups])
    if len(centres) < 2:
        return None
    return [float(np.median([c[i] for c in centres])) for i in range(5)]


def _erase_rules(crop: Image.Image) -> Image.Image:
    """Whiten table rules: pixel columns/rows that are mostly dark."""
    arr = np.asarray(crop.convert("L")).copy()
    dark = arr < 128
    arr[:, dark.mean(axis=0) > 0.5] = 255
    arr[dark.mean(axis=1) > 0.5, :] = 255
    return Image.fromarray(arr)


def _text_band(crop: Image.Image, h: float) -> Image.Image:
    """The run of inked pixel rows nearest the crop's vertical centre."""
    ink = (np.asarray(crop) < 128).sum(axis=1) > 1
    bands, start = [], None
    for y, on in enumerate([*ink, False]):
        if on and start is None:
            start = y
        elif not on and start is not None:
            bands.append((start, y))
            start = None
    bands = [b for b in bands if b[1] - b[0] >= 0.4 * h]
    if not bands:
        return crop
    mid = crop.height / 2
    y0, y1 = min(bands, key=lambda b: abs((b[0] + b[1]) / 2 - mid))
    pad = int(0.3 * h)
    return crop.crop((0, max(0, y0 - pad), crop.width, min(crop.height, y1 + pad)))


def _cell(
    image: Image.Image,
    box: tuple[float, float, float, float],
    h: float,
    scale: int,
    band: bool,
) -> int | None:
    crop = _erase_rules(image.crop(tuple(int(v) for v in box)))
    crop = _text_band(crop, h) if band else crop
    if scale > 1:
        crop = crop.resize((crop.width * scale, crop.height * scale), Image.LANCZOS)
    out = _tesseract(crop, "--psm", "7", "-c", "tessedit_char_whitelist=0123456789 ,.")
    return _per_litre(re.sub(r"\D", "", out))


def _row_cells(line: list[dict], cols: list[float], half_w: float) -> list[list[dict]]:
    cells: list[list[dict]] = [[] for _ in cols]
    for w in line:
        cx = w["x"] + w["w"] / 2
        i = min(range(len(cols)), key=lambda k: abs(cols[k] - cx))
        if abs(cols[i] - cx) < half_w and re.sub(r"\D", "", w["text"]):
            cells[i].append(w)
    return cells


def _digits(cell: list[dict]) -> str:
    return "".join(re.sub(r"\D", "", w["text"]) for w in cell)


def read_page(image: Image.Image) -> dict | None:
    """Page text and, per product, XOF/L readings by source; None if no price row.

    Sources: the F CFA/m3 row from the page OCR; the same cell cropped wide
    (then cut to its text band) and tight, each OCR'd alone at 1x and 2x; and
    the F CFA/litre row from the page OCR, which older structures carry.
    """
    words = _words(image)
    lines = _lines(words)
    texts = [ascii_lower(" ".join(w["text"] for w in ln)) for ln in lines]
    anchor = next((i for i, t in enumerate(texts) if "consommat" in t), None)
    if anchor is None:
        anchor = next(
            (i + 1 for i, t in enumerate(texts) if "marge" in t and "detaill" in t),
            None,
        )
    if anchor is None:
        return None
    cols = _columns(words, min(w["y"] for w in lines[min(anchor, len(lines) - 1)]))
    if cols is None:
        return None
    half_w = (cols[-1] - cols[0]) / (2 * (len(cols) - 1))
    m3_row: list[list[dict]] | None = None
    first_numeric: list[list[dict]] | None = None
    litre: list[int | None] = [None] * len(cols)
    for line in lines[anchor : anchor + 5]:
        cells = _row_cells(line, cols, half_w)
        lens = [len(_digits(c)) for c in cells if c]
        if first_numeric is None and lens:
            first_numeric = cells
        if m3_row is None and sum(n in (6, 7) for n in lens) >= 2:
            m3_row = cells
        elif m3_row is not None and sum(n in (3, 4) for n in lens) >= 2:
            litre = [
                _per_litre(_digits(c)) if len(_digits(c)) <= 4 else None for c in cells
            ]
            break
    m3_row = m3_row or first_numeric
    if m3_row is None:
        return None
    row_words = [w for c in m3_row for w in c]
    cy = float(np.median([w["y"] + w["h"] / 2 for w in row_words]))
    hh = float(
        np.median(
            [w["h"] for w in words if re.fullmatch(r"\d{3}", w["text"])]
            or [w["h"] for w in row_words]
        )
    )
    readings = {}
    for i, product in enumerate(PRODUCTS):
        cell = m3_row[i]
        if cell:
            x0 = min(w["x"] for w in cell) - hh
            x1 = max(w["x"] + w["w"] for w in cell) + hh
        else:
            x0, x1 = cols[i] - half_w, cols[i] + half_w
        wide = (x0, cy - 2.5 * hh, x1, cy + 2.5 * hh)
        tight = (x0, cy - hh, x1, cy + hh)
        full = _per_litre(_digits(cell)) if len(_digits(cell)) >= 6 else None
        readings[product] = [
            [full],
            *(
                [_cell(image, b, hh, s, b is wide) for s in (1, 2)]
                for b in (wide, tight)
            ),
            [litre[i]],
        ]
    return {"text": "\n".join(texts), "readings": readings}


def accept(sources: list[list[int | None]]) -> int | None:
    """The price if 2+ independent sources read it and no in-range reading differs.

    A source is one way of reading the cell (page line, wide crop, tight crop,
    litre row); its 1x and 2x OCR of the same crop count once.
    """
    values = [
        {r for r in readings if r is not None and _MIN_XOF <= r <= _MAX_XOF}
        for readings in sources
    ]
    found = [v for v in values if v]
    if len(found) < 2 or len(set().union(*found)) != 1:
        return None
    return next(iter(found[0]))
