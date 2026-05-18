"""ARENE Mozambique regulated petroleum-price comunicados."""

from __future__ import annotations

import io
import logging
import os
import re
import subprocess
import tempfile
import time
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urljoin

import pandas as pd
from bs4 import BeautifulSoup
from PIL import Image

from core.http import make_session

logger = logging.getLogger(__name__)

_BASE_URL = "https://arene.org.mz"
_INDEX_URL = f"{_BASE_URL}/noticias-e-comunicados/comunicados/"
_HISTORICAL_URL = (
    f"{_BASE_URL}/wp-content/uploads/2026/04/"
    "Evolucao-de-Precos-dos-Produtos-Petroliferos-2010-2026.pdf"
)
_COUNTRY = "Mozambique"
_CURRENCY = "MZN"
_SOURCE_KEY = "mz_arene_comunicados"
_UNIT = "litre"
_THROTTLE_S = 1.0
_MAX_INDEX_PAGES = 12

_FUEL_LINK_RE = re.compile(
    r"(pre[cç]os?.*(produto|combust|petrol)|combust[ií]veis|"
    r"comunicado.*imprensa|actualiza[cç][aã]o.*pre[cç]os?|"
    r"revis[aã]o.*pre[cç]os?)",
    re.IGNORECASE,
)
_PDF_RE = re.compile(r"\.pdf(?:$|[?#])", re.IGNORECASE)
_DATE_NUM_RE = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](20\d{2}|19\d{2})\b")
_DATE_LONG_RE = re.compile(
    r"\b(\d{1,2})\s+de\s+([A-Za-zçÇãÃ]+)\s+de\s+(\d{4})\b",
    re.IGNORECASE,
)
_FILENAME_DATE_RE = re.compile(r"(\d{1,2})[._-](\d{1,2})[._-](20\d{2})")

_MONTHS_PT = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "março": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}
_PRODUCT_PATTERNS = [
    ("Gasolina", re.compile(r"\bgasolina\b", re.IGNORECASE)),
    ("Gasóleo", re.compile(r"\bgas[oó]leo\b", re.IGNORECASE)),
    (
        "Petróleo iluminante",
        re.compile(r"\bpetr[oó]leo\s+(?:de\s+)?ilumina", re.IGNORECASE),
    ),
    ("Jet A-1", re.compile(r"\bjet\s*a[\s-]*1\b", re.IGNORECASE)),
    ("GPL", re.compile(r"\bGPL\b|g[aá]s\s+de\s+cozinha", re.IGNORECASE)),
]


def _parse_number(raw: str | None) -> float | None:
    if raw is None:
        return None
    value = raw.strip().replace(" ", "")
    if "," in value and "." in value:
        value = value.replace(".", "").replace(",", ".")
    else:
        value = value.replace(",", ".")
    try:
        out = float(value)
    except ValueError:
        return None
    return out if out > 0 else None


def _parse_date(text: str) -> date | None:
    m = _DATE_LONG_RE.search(text)
    if m:
        month = _MONTHS_PT.get(m.group(2).lower())
        if month:
            try:
                return date(int(m.group(3)), month, int(m.group(1)))
            except ValueError:
                pass
    m = _DATE_NUM_RE.search(text)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    m = _FILENAME_DATE_RE.search(unquote(text))
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    return None


def _discover_candidate_pdfs(session) -> list[tuple[str, date | None]]:
    seen: dict[str, date | None] = {}
    for page in range(1, _MAX_INDEX_PAGES + 1):
        url = _INDEX_URL if page == 1 else urljoin(_INDEX_URL, f"page/{page}/")
        if page > 1:
            time.sleep(_THROTTLE_S)
        try:
            resp = session.get(url, timeout=30)
        except Exception:
            logger.exception("[mz_arene] index request failed: %s", url)
            break
        if resp.status_code != 200:
            break
        soup = BeautifulSoup(resp.text, "lxml")
        page_links = 0
        for a in soup.find_all("a", href=True):
            href = urljoin(url, a["href"])
            label = " ".join(a.stripped_strings) or href
            if not _FUEL_LINK_RE.search(label + " " + href):
                continue
            page_links += 1
            if _PDF_RE.search(href):
                seen.setdefault(href, _parse_date(label + " " + href))
                continue
            try:
                article = session.get(href, timeout=30)
            except Exception:
                logger.exception("[mz_arene] article request failed: %s", href)
                continue
            if article.status_code != 200:
                continue
            article_soup = BeautifulSoup(article.text, "lxml")
            article_date = _parse_date(article_soup.get_text(" ", strip=True))
            for pdf_a in article_soup.find_all("a", href=True):
                pdf_url = urljoin(href, pdf_a["href"])
                if _PDF_RE.search(pdf_url):
                    seen.setdefault(pdf_url, article_date or _parse_date(pdf_url))
        logger.info(
            "[mz_arene] index page=%d fuel_links=%d pdfs=%d",
            page,
            page_links,
            len(seen),
        )
        if page > 1 and page_links == 0:
            break
    seen.setdefault(_HISTORICAL_URL, None)
    return sorted(seen.items(), key=lambda kv: (kv[1] or date.min, kv[0]))


def _pdf_text_with_pdfplumber(pdf_bytes: bytes, page_index: int | None = None) -> str:
    try:
        import pdfplumber
    except ImportError:
        return ""
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages = (
                pdf.pages
                if page_index is None
                else pdf.pages[page_index : page_index + 1]
            )
            return "\n".join((page.extract_text() or "") for page in pages)
    except Exception:
        return ""


def _pdf_page_count(pdf_bytes: bytes) -> int:
    try:
        import pdfplumber
    except ImportError:
        return 0
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            return len(pdf.pages)
    except Exception:
        return 0


def _image_to_text(image: Image.Image, lang: str = "por") -> str:
    try:
        import pytesseract

        return pytesseract.image_to_string(image, lang=lang)
    except Exception as exc:
        logger.debug("[mz_arene] pytesseract failed (%s); trying CLI", exc)
    with tempfile.TemporaryDirectory() as tmp:
        img_path = Path(tmp) / "page.png"
        out_base = Path(tmp) / "ocr"
        image.save(img_path)
        try:
            subprocess.run(
                ["tesseract", str(img_path), str(out_base), "-l", lang],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            return out_base.with_suffix(".txt").read_text(
                encoding="utf-8", errors="ignore"
            )
        except Exception as exc:
            logger.warning("[mz_arene] OCR failed with lang=%s: %s", lang, exc)
            return ""


def _pdf_page_ocr(pdf_bytes: bytes, page_index: int) -> str:
    try:
        from pdf2image import convert_from_bytes

        images = convert_from_bytes(
            pdf_bytes, first_page=page_index + 1, last_page=page_index + 1, dpi=220
        )
        if images:
            return _image_to_text(images[0], lang="por")
    except Exception as exc:
        logger.debug("[mz_arene] pdf2image failed (%s); trying pdftoppm", exc)
    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = Path(tmp) / "in.pdf"
        prefix = Path(tmp) / "page"
        pdf_path.write_bytes(pdf_bytes)
        try:
            subprocess.run(
                [
                    "pdftoppm",
                    "-f",
                    str(page_index + 1),
                    "-singlefile",
                    "-r",
                    "220",
                    "-png",
                    str(pdf_path),
                    str(prefix),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            return _image_to_text(Image.open(prefix.with_suffix(".png")), lang="por")
        except Exception as exc:
            logger.warning("[mz_arene] pdftoppm fallback failed: %s", exc)
            return ""


def _extract_product_prices(text: str) -> dict[str, float]:
    prices: dict[str, float] = {}
    number_re = re.compile(r"(?<!\d)(\d{1,3}(?:[.,]\d{1,3})?)(?!\d)")
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        for label, product_re in _PRODUCT_PATTERNS:
            if label in prices or not product_re.search(line):
                continue
            nums = [_parse_number(m.group(1)) for m in number_re.finditer(line)]
            nums = [n for n in nums if n and 10 <= n <= 500]
            if nums:
                prices[label] = nums[-1]
    return prices


def _extract_date_price_rows(text: str) -> list[tuple[date, dict[str, float]]]:
    rows: list[tuple[date, dict[str, float]]] = []
    product_order = ["Gasolina", "Gasóleo", "Petróleo iluminante", "Jet A-1", "GPL"]
    line_re = re.compile(
        r"(\d{1,2}[./-]\d{1,2}[./-]\d{4})\s+"
        r"((?:\d{1,3}(?:[.,]\d{1,3})?\s+){2,6}\d{1,3}(?:[.,]\d{1,3})?)"
    )
    for match in line_re.finditer(text):
        obs_date = _parse_date(match.group(1))
        if obs_date is None:
            continue
        nums = [
            _parse_number(n)
            for n in re.findall(r"\d{1,3}(?:[.,]\d{1,3})?", match.group(2))
        ]
        vals = [n for n in nums if n and 10 <= n <= 500]
        if len(vals) >= 3:
            rows.append((obs_date, dict(zip(product_order, vals))))
    return rows


def _download_pdf(session, url: str) -> bytes | None:
    try:
        resp = session.get(url, timeout=90)
    except Exception:
        logger.exception("[mz_arene] download failed: %s", url)
        return None
    if resp.status_code != 200 or not resp.content.startswith(b"%PDF"):
        logger.warning("[mz_arene] not a PDF: %s HTTP=%d", url, resp.status_code)
        return None
    return resp.content


def _append_rows(rows: list[dict], obs_date: date, prices: dict[str, float]) -> None:
    for product, price in prices.items():
        rows.append(
            {
                "observation_date": obs_date.isoformat(),
                "country": _COUNTRY,
                "fuel_product": product,
                "price_local": price,
                "currency": _CURRENCY,
                "source_key": _SOURCE_KEY,
                "unit": _UNIT,
            }
        )


def fetch_mz_arene(cutoff: date) -> pd.DataFrame | None:
    session = make_session()
    rows: list[dict] = []
    for i, (url, link_date) in enumerate(_discover_candidate_pdfs(session)):
        if i > 0:
            time.sleep(_THROTTLE_S)
        pdf_bytes = _download_pdf(session, url)
        if pdf_bytes is None:
            continue
        if url == _HISTORICAL_URL:
            text = _pdf_text_with_pdfplumber(pdf_bytes) or "\n".join(
                _pdf_page_ocr(pdf_bytes, p) for p in range(_pdf_page_count(pdf_bytes))
            )
            for obs_date, prices in _extract_date_price_rows(text):
                if obs_date > cutoff:
                    _append_rows(rows, obs_date, prices)
            continue
        if link_date is not None and link_date <= cutoff:
            continue
        text = _pdf_text_with_pdfplumber(pdf_bytes, page_index=2) or _pdf_page_ocr(
            pdf_bytes, page_index=2
        )
        obs_date = link_date or _parse_date(text) or _parse_date(os.path.basename(url))
        if obs_date is None or obs_date <= cutoff:
            continue
        prices = _extract_product_prices(text)
        if not prices:
            logger.warning("[mz_arene] no product prices parsed from %s", url)
            continue
        _append_rows(rows, obs_date, prices)
    if not rows:
        logger.info("[mz_arene] no rows after cutoff %s", cutoff)
        return None
    df = (
        pd.DataFrame(rows)
        .drop_duplicates(subset=["observation_date", "fuel_product"], keep="last")
        .sort_values(["observation_date", "fuel_product"])
        .reset_index(drop=True)
    )
    logger.info(
        "[mz_arene] %d rows (%s → %s)",
        len(df),
        df["observation_date"].iloc[0],
        df["observation_date"].iloc[-1],
    )
    return df


__all__ = ["fetch_mz_arene"]
