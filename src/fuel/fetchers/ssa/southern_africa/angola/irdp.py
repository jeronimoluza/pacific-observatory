"""IRDP Angola quarterly petroleum fuel-price reports.

The Instituto Regulador dos Derivados do Petróleo publishes first-party
``Relatório dos Combustíveis`` PDFs from the homepage. Quarterly reports carry
fixed public retail prices for gasoline, diesel, illuminating kerosene and LPG,
plus Jet A-1 reference prices. Recent reports expose Jet A-1 as a three-month
quarterly table; older reports expose only the current month's Jet A-1 values.
"""

from __future__ import annotations

import io
import logging
import re
import time
import unicodedata
import warnings
from datetime import date
from urllib.parse import unquote, urljoin

import pandas as pd
import requests
import urllib3
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.irdp.gov.ao"
_INDEX_URL = f"{_BASE_URL}/"
_COUNTRY = "Angola"
_CURRENCY = "AOA"
_SOURCE_KEY = "irdp_ao_quarterly"
_THROTTLE_S = 0.6

_STATIC_REPORTS = [
    (
        "/images/relatorios/2022/RELATRIO_TRIMESTRAL_SOBRE_OS_COMBUSTVEIS_I_TRIMESTRE_2022_VF310320221.pdf",
        date(2022, 1, 1),
    ),
    (
        "/images/relatorios/2022/Relatorio_dos_Combustveis_-_II_Trimestre_2022.pdf",
        date(2022, 4, 1),
    ),
    (
        "/images/relatorios/2022/Relatorio_dos_Combustveis_-_III_Trimestre_2022.pdf",
        date(2022, 7, 1),
    ),
    (
        "/images/relatorios/2022/Relatorio_dos_Combustveis_-_IV_Trimestre_2022.pdf",
        date(2022, 10, 1),
    ),
    ("/images/relatorios/Combustiveis_I_Trimestre.pdf", date(2023, 1, 1)),
    ("/images/relatorios/Combustveis_II_Trimestre.pdf", date(2023, 4, 1)),
    (
        "/images/relatorios/Relatorio_dos_Combustveis_III_Trimestre.pdf",
        date(2023, 7, 1),
    ),
    (
        "/images/relatorios/Relatorio_dos_Combustveis_IV_Trimestre_2023.pdf",
        date(2023, 10, 1),
    ),
    (
        "/images/relatorios/Relatorio_dos_Combustveis_-_I_Trimestre_2024.pdf",
        date(2024, 1, 1),
    ),
    (
        "/images/relatorios/Relatorio_dos_Combustveis_-_II_Trimestre_2024.pdf",
        date(2024, 4, 1),
    ),
    (
        "/images/relatorios/Relatorio_dos_Combustveis_-_III_Trimestre_2024.pdf",
        date(2024, 7, 1),
    ),
]

_QUARTER_START = {1: (1, 1), 2: (4, 1), 3: (7, 1), 4: (10, 1)}
_QUARTER_MONTHS = {
    1: [1, 2, 3],
    2: [4, 5, 6],
    3: [7, 8, 9],
    4: [10, 11, 12],
}
_MONTH_ALIASES = {
    "jan": 1,
    "janeiro": 1,
    "fev": 2,
    "fevereiro": 2,
    "mar": 3,
    "marco": 3,
    "março": 3,
    "abr": 4,
    "abril": 4,
    "mai": 5,
    "maio": 5,
    "jun": 6,
    "junho": 6,
    "jul": 7,
    "julho": 7,
    "ago": 8,
    "agosto": 8,
    "set": 9,
    "setembro": 9,
    "out": 10,
    "outubro": 10,
    "nov": 11,
    "novembro": 11,
    "dez": 12,
    "dezembro": 12,
}
_PRODUCTS = {
    "Gasolina": (re.compile(r"\bGasolina\b", re.I), "L"),
    "Gasóleo": (re.compile(r"\bGas[oó]leo\b", re.I), "L"),
    "Petróleo Iluminante": (re.compile(r"\bPetr[oó]leo\s+Iluminante\b", re.I), "L"),
    "GPL": (re.compile(r"\bGPL\b.*?(?:Liquefeito)?", re.I), "kg"),
}
_JET_LABELS = [
    re.compile(r"Pre[çc]o\s+de\s+Refer[eê]ncia\s+do\s+Ajustamento.*?\(PRA\)", re.I),
    re.compile(r"Pre[çc]o\s+Base\s+na\s+Costa.*?\(PBC\)", re.I),
    re.compile(r"Pre[çc]o\s+de\s+Venda\s+Ex[-\s]Log[ií]stica.*?\(PVD\)", re.I),
    re.compile(r"Pre[çc]o\s+da\s+Aero[-\s]?instala[çc][aã]o.*?\(PVA\)", re.I),
]
_NUMBER_RE = re.compile(r"\d[\d\s.]*,\d+|\d[\d\s.]*(?:\.\d+)?")


def _normalize(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    ).lower()


def _parse_number(raw: str | None) -> float | None:
    if raw is None:
        return None
    value = raw.replace("\xa0", " ").strip()
    value = re.sub(r"\s+", "", value)
    if "," in value:
        value = value.replace(".", "").replace(",", ".")
    try:
        out = float(value)
    except ValueError:
        return None
    return out if out > 0 else None


def _get(
    session: requests.Session, url: str, timeout: int = 60
) -> requests.Response | None:
    try:
        return session.get(url, timeout=timeout)
    except requests.exceptions.SSLError:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", urllib3.exceptions.InsecureRequestWarning)
            return session.get(url, timeout=timeout, verify=False)
    except Exception as exc:
        logger.warning("[irdp_ao] request failed: %s (%s)", url, exc)
        return None


def _quarter_from_slug(text: str) -> tuple[int, int] | None:
    slug = _normalize(unquote(text)).replace("-", "_")
    year_match = re.search(r"(20\d{2})", slug)
    if not year_match:
        return None
    year = int(year_match.group(1))
    if re.search(r"(?:iv|4|4o|4º|quarto)_?trimestre", slug):
        return year, 4
    if re.search(r"(?:iii|3|3o|3º|terceiro)_?trimestre", slug):
        return year, 3
    if re.search(r"(?:ii|2|2o|2º|segundo)_?trimestre", slug):
        return year, 2
    if re.search(r"(?:i|1|1o|1º|primeiro)_?trimestre", slug):
        return year, 1
    return None


def _discover_reports(session: requests.Session) -> list[tuple[str, date]]:
    found: dict[str, date] = {}
    resp = _get(session, _INDEX_URL)
    if resp is not None and resp.status_code == 200:
        soup = BeautifulSoup(resp.text, "lxml")
        for anchor in soup.find_all("a", href=True):
            href = urljoin(_INDEX_URL, anchor["href"])
            label = " ".join(anchor.stripped_strings)
            haystack = f"{label} {href}"
            if ".pdf" not in href.lower():
                continue
            if "/images/relatorios/" not in href and "/images/Relatorio_" not in href:
                continue
            parsed = _quarter_from_slug(haystack)
            if not parsed:
                continue
            year, quarter = parsed
            month, day = _QUARTER_START[quarter]
            found[href] = date(year, month, day)
    for path, obs_date in _STATIC_REPORTS:
        url = urljoin(_BASE_URL, path)
        found.setdefault(url, obs_date)
    return sorted(found.items(), key=lambda item: (item[1], item[0]))


def _pdf_pages(pdf_bytes: bytes) -> list[str]:
    try:
        import pdfplumber
    except ImportError:
        logger.error("[irdp_ao] pdfplumber not installed")
        return []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            return [page.extract_text() or "" for page in pdf.pages]
    except Exception:
        logger.exception("[irdp_ao] PDF parse failed")
        return []


def _extract_fixed_prices(text: str, obs_date: date) -> list[dict]:
    rows: list[dict] = []
    for label, (pattern, unit) in _PRODUCTS.items():
        match = pattern.search(text)
        if not match:
            continue
        tail = text[match.end() : match.end() + 80]
        price_match = _NUMBER_RE.search(tail)
        price = _parse_number(price_match.group(0) if price_match else None)
        if price is None:
            continue
        rows.append(
            {
                "observation_date": obs_date.isoformat(),
                "country": _COUNTRY,
                "fuel_product": label,
                "price_local": price,
                "currency": _CURRENCY,
                "source_key": _SOURCE_KEY,
                "unit": unit,
            }
        )
    return rows


def _extract_month_headers(text: str) -> list[int]:
    for raw_line in text.splitlines():
        line = _normalize(raw_line)
        months = []
        for token in re.findall(r"[a-zçãéíóú]+", line):
            month = _MONTH_ALIASES.get(token)
            if month and month not in months:
                months.append(month)
        if len(months) >= 3:
            return months[:3]
    return []


def _month_from_single_jet_page(text: str, default_year: int) -> int | None:
    match = re.search(
        r"a\s+partir\s+de\s+1\s+de\s+([A-Za-zçÇãÃéÉ]+)(?:\s+de\s+|\s+)(20\d{2})?",
        text,
        re.I,
    )
    if not match:
        return None
    month = _MONTH_ALIASES.get(_normalize(match.group(1)))
    year = int(match.group(2)) if match.group(2) else default_year
    if year != default_year:
        return None
    return month


def _extract_jet_prices(text: str, report_date: date) -> list[dict]:
    rows: list[dict] = []
    months = _extract_month_headers(text)
    for pattern in _JET_LABELS:
        match = pattern.search(text)
        if not match:
            continue
        tail = text[match.end() : match.end() + 180]
        values = [_parse_number(m.group(0)) for m in _NUMBER_RE.finditer(tail)]
        values = [v for v in values if v is not None and 100 <= v <= 2000]
        if len(months) >= 3 and len(values) >= 3:
            for month, price in zip(months[:3], values[:3]):
                rows.append(
                    {
                        "observation_date": date(
                            report_date.year, month, 1
                        ).isoformat(),
                        "country": _COUNTRY,
                        "fuel_product": "Jet A-1",
                        "price_local": price,
                        "currency": _CURRENCY,
                        "source_key": _SOURCE_KEY,
                        "unit": "L",
                    }
                )
        elif values:
            month = _month_from_single_jet_page(text, report_date.year)
            if month is None:
                quarter = ((report_date.month - 1) // 3) + 1
                month = _QUARTER_MONTHS[quarter][-1]
            rows.append(
                {
                    "observation_date": date(report_date.year, month, 1).isoformat(),
                    "country": _COUNTRY,
                    "fuel_product": "Jet A-1",
                    "price_local": values[0],
                    "currency": _CURRENCY,
                    "source_key": _SOURCE_KEY,
                    "unit": "L",
                }
            )
    return rows


def _extract_report_rows(pdf_bytes: bytes, obs_date: date) -> list[dict]:
    fixed_rows: list[dict] = []
    jet_rows: list[dict] = []
    for text in _pdf_pages(pdf_bytes):
        if "Preços de Venda Fixados" in text or "Produtos Preço de Venda" in text:
            fixed_rows.extend(_extract_fixed_prices(text, obs_date))
        if "JET A1" in text or "JET A 1" in text or "JET-A1" in text:
            jet_rows.extend(_extract_jet_prices(text, obs_date))
    return fixed_rows + jet_rows


def fetch_irdp_ao(cutoff: date) -> pd.DataFrame | None:
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    rows: list[dict] = []
    for url, obs_date in _discover_reports(session):
        time.sleep(_THROTTLE_S)
        resp = _get(session, url, timeout=90)
        if (
            resp is None
            or resp.status_code != 200
            or not resp.content.startswith(b"%PDF")
        ):
            logger.info("[irdp_ao] PDF unavailable: %s", url)
            continue
        parsed = _extract_report_rows(resp.content, obs_date)
        if not parsed:
            logger.warning("[irdp_ao] no prices parsed from %s", url)
            continue
        rows.extend(parsed)
        logger.info("[irdp_ao] %s -> %d rows", url.rsplit("/", 1)[-1], len(parsed))
    if not rows:
        logger.info("[irdp_ao] no rows after cutoff %s", cutoff)
        return None
    df = (
        pd.DataFrame(rows)
        .drop_duplicates(subset=["observation_date", "fuel_product"], keep="last")
        .sort_values(["observation_date", "fuel_product"])
        .reset_index(drop=True)
    )
    logger.info(
        "[irdp_ao] %d rows (%s -> %s)",
        len(df),
        df["observation_date"].iloc[0],
        df["observation_date"].iloc[-1],
    )
    return df


__all__ = ["fetch_irdp_ao"]
