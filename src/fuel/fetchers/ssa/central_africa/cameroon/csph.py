"""CSPH Cameroon monthly official fuel-price structure PDFs.

The Caisse de Stabilisation des Prix des Hydrocarbures publishes first-party
monthly price-structure PDFs for regulated petroleum products. The fetcher
probes current CSPH pages and deterministic monthly PDF slugs, then uses the
Wayback CDX archive for historical CSPH PDFs under the same first-party paths.
PDFs are read with pdfplumber when text is selectable and OCR is used as a
fallback for scanned pages.
"""

from __future__ import annotations

import hashlib
import io
import logging
import re
import subprocess
import tempfile
import time
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import pandas as pd
import urllib3
from bs4 import BeautifulSoup
from PIL import Image

from core.http import make_session

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_OCR_CACHE_DIR = (
    Path(__file__).resolve().parents[6]
    / "data"
    / "fuel"
    / "ssa"
    / "central_africa"
    / "cameroon"
    / "csph"
    / "_ocr_cache"
)

logger = logging.getLogger(__name__)

_COUNTRY = "Cameroon"
_CURRENCY = "XAF"
_SOURCE_KEY = "csph_cm_monthly"
_BASE_HOSTS = ("https://csph.cm", "https://www.csph.cm")
_INDEX_URLS = (
    "https://csph.cm/",
    "https://www.csph.cm/",
    "https://www.csph.cm/index.php/fr/",
    "https://www.csph.cm/index.php/en/",
    "https://www.csph.cm/pricestructure.php",
    "https://www.csph.cm/pricestructure.php?lang=en",
)
_CDX_URL = (
    "https://web.archive.org/cdx/search/cdx?"
    "url=csph.cm&matchType=domain&output=json&filter=statuscode:200"
)
_WAYBACK_FMT = "https://web.archive.org/web/{ts}id_/{url}"
_THROTTLE_S = 0.6
_CURRENT_YEAR = date.today().year
_LIVE_PDF_BASE = "https://csph.cm/dashboard/assets/uploads/pdfs/"
_PDF_PATH_RE = re.compile(
    r"csph\.cm/(?:images/publications/(?:price_structure|structure_des_prix)/|"
    r"dashboard/assets/uploads/pdfs/).+?\.pdf",
    re.I,
)
_PRICE_DOC_RE = re.compile(
    r"(?:structure|prix|price|carburant|fuel|petrole|p[ée]trole|gasoil|super|gpl|lpg|butane)",
    re.I,
)
_NUMBER_RE = re.compile(r"(?<!\d)(\d{1,5}(?:[,.]\d{1,3})?)(?!\d)")
_SPACED_NUMBER_RE = re.compile(r"(?<!\d)(\d{1,3}(?:\s\d{3})+)(?!\d)")
_PRODUCT_ORDER = ("Super", "Pétrole Lampant", "Gasoil")
_PRODUCT_PATTERNS = (
    ("Super", re.compile(r"\bsuper\b|essence\s+super", re.I)),
    ("Gasoil", re.compile(r"\bgasoil\b|gas\s*oil|diesel", re.I)),
    (
        "Pétrole Lampant",
        re.compile(
            r"p[ée]trole\s+lampant|\bpetrole\b|\bkerosene\b|\bk[ée]ros[èe]ne\b", re.I
        ),
    ),
    ("Gaz Butane", re.compile(r"gaz\s+butane|butane|gpl|lpg|gaz\s+domestique", re.I)),
)
_RETAIL_LABELS = (
    "prix de detail ttc",
    "prix detail ttc",
    "prix de vente au detail",
    "prix vente detail",
    "prix a la pompe",
    "prix pompe",
    "prix public",
    "prix consommateur",
    "prix final",
)
_DEPOT_LABELS = (
    "prix sortie depot ttc",
    "prix sortie depot de douala ttc",
)
_DEPOT_LABEL_RE = re.compile(
    r"(?:prix\s+sortie\s+d[ée]?p[oô]?t(?:\s+d[ée]?\s*\w+)?\s+ttc"
    r"|(?:\w+\s+)?depot\s+exit\s+price\s+(?:including|excluding)\s+taxes"
    r"|exit\s+price\s+(?:including|excluding)\s+taxes"
    r"|(?:\w+\s+)?wholesale\s+price[s]?\s+(?:including|excluding)\s+taxes"
    r"|prix\s+de\s+gros\s+(?:[àa]\s+\w+\s+)?(?:ht|ttc))",
    re.I,
)
_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
    "janvier": 1,
    "fevrier": 2,
    "février": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "août": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
    "décembre": 12,
}
_EN_MONTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
_FR_MONTH_NAMES = (
    "JANVIER",
    "FEVRIER",
    "MARS",
    "AVRIL",
    "MAI",
    "JUIN",
    "JUILLET",
    "AOUT",
    "SEPTEMBRE",
    "OCTOBRE",
    "NOVEMBRE",
    "DECEMBRE",
)


def _ascii(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", _ascii(text).lower()).strip()


def _parse_number(raw: str | None) -> float | None:
    if raw is None:
        return None
    cleaned = raw.replace(" ", "").strip()
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "." in cleaned and re.search(r"\.\d{3}$", cleaned):
        cleaned = cleaned.replace(".", "")
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return value if 50 <= value <= 100000 else None


def _numbers(line: str, low: float = 50, high: float = 100000) -> list[float]:
    vals = [_parse_number(m.group(1)) for m in _NUMBER_RE.finditer(line)]
    return [v for v in vals if v is not None and low <= v <= high]


def _date_from_month_year(month_text: str, year_text: str) -> date | None:
    month = _MONTHS.get(month_text.lower())
    if not month:
        month = _MONTHS.get(_ascii(month_text).lower())
    if not month:
        return None
    year = int(year_text)
    if year < 2010 or year > _CURRENT_YEAR + 1:
        return None
    return date(year, month, 1)


def _date_from_url(url: str) -> date | None:
    decoded = unquote(urlparse(url).path)
    name = Path(decoded).stem
    spaced = re.sub(r"[_\-\s]+", " ", name).strip()
    match = re.search(r"([A-Za-zéûÉÛ]+)\s+(20\d{2})", spaced, re.I)
    if match:
        return _date_from_month_year(match.group(1), match.group(2))
    return None


def _date_from_text(text: str) -> date | None:
    patterns = (
        r"(?:du\s+)?(?:1er|1|01)\s+(?:au\s+\d{1,2}\s+)?([A-Za-zéûÉÛ]+)\s+(20\d{2})",
        r"([A-Za-zéûÉÛ]+)\s+(20\d{2})",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.I):
            parsed = _date_from_month_year(match.group(1), match.group(2))
            if parsed:
                return parsed
    return None


def _normalize_pdf_url(url: str, base_url: str) -> str | None:
    joined = urljoin(base_url, url)
    parsed = urlparse(joined)
    if not parsed.netloc.lower().endswith("csph.cm"):
        return None
    if ".pdf" not in parsed.path.lower():
        return None
    if not _PRICE_DOC_RE.search(unquote(joined)):
        return None
    return joined.split("#", 1)[0]


def _fetch_html(session, url: str) -> str | None:
    try:
        resp = session.get(url, timeout=45)
    except Exception:
        logger.exception("[csph_cm] HTML request failed: %s", url)
        return None
    if resp.status_code != 200:
        logger.warning("[csph_cm] HTTP %d for %s", resp.status_code, url)
        return None
    return resp.text


def _host_reachable(session) -> bool:
    for url in ("https://web.archive.org/", "https://csph.cm/"):
        try:
            session.get(url, timeout=10)
            return True
        except Exception:
            continue
    return False


def _discover_from_html(html: str, page_url: str) -> set[str]:
    soup = BeautifulSoup(html, "lxml")
    urls: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        label = " ".join(anchor.stripped_strings)
        candidate = _normalize_pdf_url(anchor["href"], page_url)
        if candidate and _PRICE_DOC_RE.search(f"{label} {candidate}"):
            urls.add(candidate)
    for match in re.finditer(r"https?://[^\"'\s<>]+\.pdf", html, re.I):
        candidate = _normalize_pdf_url(match.group(0), page_url)
        if candidate:
            urls.add(candidate)
    return urls


def _candidate_slug_urls(cutoff: date) -> set[str]:
    """Enumerate plausible live CSPH PDF URLs in /dashboard/assets/uploads/pdfs/.

    Legacy /images/publications/... paths return HTML stubs on the live site so
    we don't probe them. Wayback's CDX list is consulted separately for digest
    metadata but most archived PDFs hit Wayback's 1 MiB replay cap and yield
    truncated bytes that fail PDF parsing — we rely on the live path here.
    """
    urls: set[str] = set()
    for year in range(cutoff.year, _CURRENT_YEAR + 1):
        for month in _EN_MONTH_NAMES:
            for variant in (month, month.upper(), month.lower()):
                urls.add(f"{_LIVE_PDF_BASE}{variant}_{year}.pdf")
        for month in _FR_MONTH_NAMES:
            for variant in (month, month.upper(), month.lower(), month.capitalize()):
                urls.add(f"{_LIVE_PDF_BASE}{variant}_{year}.pdf")
    return urls


def _wayback_pdf_urls(session, cutoff: date) -> dict[str, list[str]]:
    from_ts = cutoff.strftime("%Y%m%d")
    to_ts = date.today().strftime("%Y%m%d")
    try:
        resp = session.get(f"{_CDX_URL}&from={from_ts}&to={to_ts}", timeout=60)
    except Exception:
        logger.exception("[csph_cm] CDX request failed")
        return {}
    if resp.status_code != 200:
        logger.warning("[csph_cm] CDX HTTP %d", resp.status_code)
        return {}
    try:
        data = resp.json()
    except Exception:
        logger.exception("[csph_cm] CDX JSON decode failed")
        return {}
    if len(data) <= 1:
        return {}
    header = [str(item).lower() for item in data[0]]
    ts_idx = header.index("timestamp") if "timestamp" in header else 1
    url_idx = header.index("original") if "original" in header else 2
    out: dict[str, list[str]] = {}
    for row in data[1:]:
        if len(row) <= max(ts_idx, url_idx):
            continue
        original = str(row[url_idx])
        if not _PDF_PATH_RE.search(original):
            continue
        if not _PRICE_DOC_RE.search(unquote(original)):
            continue
        out.setdefault(original, []).append(str(row[ts_idx]))
    return out


def _download_pdf(session, url: str) -> bytes | None:
    """Stream a candidate URL; abort early if the first bytes aren't a PDF magic."""
    try:
        resp = session.get(url, timeout=(15, 90), stream=True)
    except Exception:
        logger.debug("[csph_cm] PDF request failed: %s", url)
        return None
    try:
        if resp.status_code != 200:
            return None
        chunks = resp.iter_content(chunk_size=8192)
        first = next(chunks, b"")
        if not first.startswith(b"%PDF"):
            return None
        body = bytearray(first)
        for chunk in chunks:
            body.extend(chunk)
        return bytes(body)
    finally:
        resp.close()


def _pdf_text(pdf_bytes: bytes) -> str:
    try:
        import pdfplumber
    except ImportError:
        return ""
    parts: list[str] = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                parts.append(page.extract_text() or "")
                for table in page.extract_tables() or []:
                    for row in table:
                        parts.append(" ".join(str(cell or "") for cell in row))
    except Exception:
        logger.exception("[csph_cm] pdfplumber extraction failed")
        return ""
    return "\n".join(parts)


def _image_to_text(image: Image.Image, lang: str = "fra") -> str:
    try:
        import pytesseract

        return pytesseract.image_to_string(image, lang=lang)
    except Exception as exc:
        logger.debug("[csph_cm] pytesseract failed with lang=%s: %s", lang, exc)
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
            logger.warning("[csph_cm] OCR failed with lang=%s: %s", lang, exc)
            return ""


_OCR_MAX_PAGES = 10


def _ocr_pdf(pdf_bytes: bytes) -> str:
    """OCR up to _OCR_MAX_PAGES — CSPH price tables sit on pages 3–8."""
    try:
        from pdf2image import convert_from_bytes

        return "\n".join(
            _image_to_text(img, lang="fra") or _image_to_text(img, lang="eng")
            for img in convert_from_bytes(pdf_bytes, dpi=220, last_page=_OCR_MAX_PAGES)
        )
    except Exception as exc:
        logger.debug("[csph_cm] pdf2image failed: %s", exc)
    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = Path(tmp) / "in.pdf"
        prefix = Path(tmp) / "page"
        pdf_path.write_bytes(pdf_bytes)
        try:
            subprocess.run(
                [
                    "pdftoppm",
                    "-r",
                    "220",
                    "-png",
                    "-f",
                    "1",
                    "-l",
                    str(_OCR_MAX_PAGES),
                    str(pdf_path),
                    str(prefix),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except Exception as exc:
            logger.warning("[csph_cm] pdftoppm fallback failed: %s", exc)
            return ""
        pages = sorted(Path(tmp).glob("page-*.png"))
        return "\n".join(
            _image_to_text(Image.open(p), lang="fra")
            or _image_to_text(Image.open(p), lang="eng")
            for p in pages
        )


def _line_product_prices(line: str) -> dict[str, float]:
    prices: dict[str, float] = {}
    matched = [
        (product, pattern)
        for product, pattern in _PRODUCT_PATTERNS
        if pattern.search(line)
    ]
    if len(matched) != 1:
        return prices
    for product, pattern in matched:
        vals = _numbers(line)
        if not vals:
            continue
        if product == "Gaz Butane":
            vals.extend(
                v
                for v in (
                    _parse_number(m.group(1)) for m in _SPACED_NUMBER_RE.finditer(line)
                )
                if v is not None
            )
            lpg_vals = [v for v in vals if 1000 <= v <= 50000]
            if lpg_vals:
                prices[product] = lpg_vals[-1]
        else:
            liquid_vals = [v for v in vals if 100 <= v <= 2000]
            if liquid_vals:
                prices[product] = liquid_vals[-1]
    return prices


def _row_prices(line: str) -> dict[str, float]:
    vals = [v for v in _numbers(line) if 100 <= v <= 2000]
    if len(vals) < 3:
        return {}
    vals = vals[-3:]
    return dict(zip(_PRODUCT_ORDER, vals))


_LOCALITY_ROW_RE = re.compile(
    r"\b(?:DA\s*0+\s*DOUALA|YE\s*0+\s*YAOUNDE|YE\s*0+\s*YAOUND[ÉE])\b",
    re.I,
)


def _locality_row_prices(text: str) -> dict[str, float]:
    """Extract retail prices from the DOUALA / YAOUNDE row of the locality table.

    Each row has 6 numbers in pairs (wholesale, retail) for Premium, Kerosene, Diesel.
    OCR may render the retail column with stray punctuation; we take the integer
    values at positions 1, 3, 5 of the parsed number sequence.
    """
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not _LOCALITY_ROW_RE.search(line):
            continue
        vals = [v for v in _numbers(line, low=50, high=2000)]
        if len(vals) < 6:
            continue
        retail = vals[1::2][:3]
        if len(retail) < 3:
            continue
        product_map = {
            "Super": retail[0],
            "Pétrole Lampant": retail[1],
            "Gasoil": retail[2],
        }
        return product_map
    return {}


def _extract_prices(text: str) -> dict[str, float]:
    locality_prices = _locality_row_prices(text)
    retail_rows: list[dict[str, float]] = []
    depot_rows: list[dict[str, float]] = []
    direct_prices: dict[str, float] = {}
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        clean = _clean(line)
        direct_prices.update(_line_product_prices(line))
        if any(label in clean for label in _RETAIL_LABELS):
            row = _row_prices(line)
            if row:
                retail_rows.append(row)
        elif _DEPOT_LABEL_RE.search(clean):
            row = _row_prices(line)
            if row:
                depot_rows.append(row)
    prices: dict[str, float] = {}
    if locality_prices:
        prices.update(locality_prices)
    if retail_rows:
        for row in retail_rows:
            for product, value in row.items():
                prices.setdefault(product, value)
    elif depot_rows and not prices:
        for row in depot_rows:
            for product, value in row.items():
                prices.setdefault(product, value)
    for product, value in direct_prices.items():
        prices.setdefault(product, value)
    return prices


def _row_for(obs_date: date, product: str, price: float) -> dict:
    unit = "cylinder" if product == "Gaz Butane" else "L"
    return {
        "observation_date": obs_date.isoformat(),
        "country": _COUNTRY,
        "fuel_product": product,
        "price_local": price,
        "currency": _CURRENCY,
        "unit": unit,
        "source_key": _SOURCE_KEY,
    }


def _fetch_pdf_with_wayback(
    session,
    url: str,
    wayback_timestamps: list[str],
) -> tuple[bytes | None, str | None]:
    pdf_bytes = _download_pdf(session, url)
    if pdf_bytes:
        return pdf_bytes, url
    for ts in sorted(set(wayback_timestamps), reverse=True):
        time.sleep(_THROTTLE_S)
        wb_url = _WAYBACK_FMT.format(ts=ts, url=url)
        pdf_bytes = _download_pdf(session, wb_url)
        if pdf_bytes:
            return pdf_bytes, wb_url
    return None, None


def fetch_csph_cm(cutoff: date) -> pd.DataFrame | None:
    session = make_session()
    # CSPH's TLS chain doesn't validate under default CA bundle; csph.cm is
    # the canonical first-party source so we accept the cert without verification.
    session.verify = False
    if not _host_reachable(session):
        logger.warning("[csph_cm] network unavailable; skipping fetch")
        return None
    discovered: dict[str, list[str]] = {}
    for url in _INDEX_URLS:
        html = _fetch_html(session, url)
        if html:
            for pdf_url in _discover_from_html(html, url):
                discovered.setdefault(pdf_url, [])
    cdx_urls = _wayback_pdf_urls(session, cutoff)
    for pdf_url, timestamps in cdx_urls.items():
        discovered.setdefault(pdf_url, []).extend(timestamps)
    for pdf_url in _candidate_slug_urls(cutoff):
        discovered.setdefault(pdf_url, [])

    rows: list[dict] = []
    seen_docs: set[str] = set()
    seen_months: set[date] = set()
    for pdf_url, timestamps in sorted(discovered.items()):
        obs_date_hint = _date_from_url(pdf_url)
        if obs_date_hint and obs_date_hint < cutoff:
            continue
        if obs_date_hint and obs_date_hint in seen_months:
            continue
        time.sleep(_THROTTLE_S)
        pdf_bytes, fetched_url = _fetch_pdf_with_wayback(session, pdf_url, timestamps)
        if not pdf_bytes or not fetched_url:
            continue
        digest = hashlib.sha256(pdf_bytes).hexdigest()[:16]
        cache_path = _OCR_CACHE_DIR / f"{digest}.txt"
        ocr_used = False
        if cache_path.exists():
            text = cache_path.read_text(encoding="utf-8", errors="ignore")
        else:
            text = _pdf_text(pdf_bytes)
            if not text.strip():
                text = _ocr_pdf(pdf_bytes)
                ocr_used = True
            try:
                _OCR_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(text, encoding="utf-8")
            except OSError:
                logger.debug("[csph_cm] could not write OCR cache to %s", cache_path)
        obs_date = obs_date_hint or _date_from_text(text)
        if obs_date is None or obs_date < cutoff:
            continue
        prices = _extract_prices(text)
        if not prices:
            logger.warning("[csph_cm] no prices parsed from %s", fetched_url)
            continue
        doc_key = f"{obs_date.isoformat()}:{sorted(prices.items())}"
        if doc_key in seen_docs:
            continue
        seen_docs.add(doc_key)
        seen_months.add(obs_date)
        for product, price in prices.items():
            rows.append(_row_for(obs_date, product, price))
        logger.info(
            "[csph_cm] %s -> %s, %d products, ocr=%s",
            fetched_url,
            obs_date,
            len(prices),
            ocr_used,
        )

    if not rows:
        logger.info("[csph_cm] no rows after cutoff %s", cutoff)
        return None
    df = (
        pd.DataFrame(rows)
        .drop_duplicates(subset=["observation_date", "fuel_product"], keep="last")
        .sort_values(["observation_date", "fuel_product"])
        .reset_index(drop=True)
    )
    logger.info(
        "[csph_cm] %d rows (%s -> %s, %d dates x %d products)",
        len(df),
        df["observation_date"].iloc[0],
        df["observation_date"].iloc[-1],
        df["observation_date"].nunique(),
        df["fuel_product"].nunique(),
    )
    return df


__all__ = ["fetch_csph_cm"]
