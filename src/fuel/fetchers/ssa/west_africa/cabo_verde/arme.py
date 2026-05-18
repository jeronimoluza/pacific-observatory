"""ARME Cabo Verde monthly maximum fuel-price articles.

ARME publishes monthly articles titled "ARME atualiza preços máximos dos
combustíveis para <month> <year>". The fetcher crawls the news category,
opens matching articles, parses the prose/table prices for gasoline,
diesel, kerosene and bulk butane, and emits CVE per litre or kg rows on
the first day of the article month.
"""

from __future__ import annotations

import logging
import re
import time
import unicodedata
from datetime import date
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup

from core.http import make_session

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.arme.cv/"
_INDEX_URL = f"{_BASE_URL}index.php?option=com_content&view=category&id=79&Itemid=878"
_COUNTRY = "Cabo Verde"
_CURRENCY = "CVE"
_SOURCE_KEY = "arme_cv_monthly"
_THROTTLE_S = 0.8
_MAX_PAGES = 80

_TITLE_RE = re.compile(
    r"arme\s+atualiza\s+pre[çc]os\s+m[áa]ximos\s+dos\s+combust[íi]veis\s+para\s+([\wçãáéíóúâêô]+)\s+(\d{4})",
    re.IGNORECASE,
)
_PRODUCT_PATTERNS = {
    "Gasolina": r"Gasolina",
    "Gasóleo": r"Gas[óo]leo(?:\s+Normal)?",
    "Petróleo": r"Petr[óo]leo",
    "Gás Butano": r"(?:G[áa]s\s+Butano|GPL)",
}
_MONTHS = {
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


def _norm(value: str) -> str:
    text = unicodedata.normalize("NFKD", value.strip().lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text)


def _month_date(month_name: str, year: str) -> date | None:
    month = _MONTHS.get(month_name.lower()) or _MONTHS.get(_norm(month_name))
    if month is None:
        return None
    try:
        return date(int(year), month, 1)
    except ValueError:
        return None


def _clean_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" "))


def _parse_number(value: str) -> float | None:
    text = value.strip().replace(".", "").replace(",", ".")
    try:
        price = float(text)
    except ValueError:
        return None
    return price if price > 0 else None


def _article_date(title_or_url: str) -> date | None:
    text = title_or_url.replace("-", " ")
    match = _TITLE_RE.search(text)
    if not match:
        return None
    return _month_date(match.group(1), match.group(2))


def _discover_articles(session) -> list[tuple[date, str]]:
    out: dict[str, date] = {}
    for offset in range(0, _MAX_PAGES * 6, 6):
        url = _INDEX_URL if offset == 0 else f"{_INDEX_URL}&limitstart={offset}"
        try:
            resp = session.get(url, timeout=45)
        except Exception:
            logger.exception("[arme_cv] index fetch failed: %s", url)
            break
        if resp.status_code != 200:
            break
        soup = BeautifulSoup(resp.text, "lxml")
        page_new = 0
        for link in soup.find_all("a", href=True):
            title = re.sub(r"\s+", " ", link.get_text(" ")).strip()
            obs_date = _article_date(title) or _article_date(link["href"])
            if obs_date is None:
                continue
            article_url = urljoin(_BASE_URL, link["href"])
            if article_url not in out:
                out[article_url] = obs_date
                page_new += 1
        logger.info(
            "[arme_cv] page offset=%d new=%d total=%d", offset, page_new, len(out)
        )
        if page_new == 0 and offset > 24:
            break
        time.sleep(_THROTTLE_S)
    return sorted((obs_date, url) for url, obs_date in out.items())


def _parse_prices(text: str) -> list[tuple[str, float, str]]:
    out: list[tuple[str, float, str]] = []
    seen: set[str] = set()
    for label, product_re in _PRODUCT_PATTERNS.items():
        pattern = re.compile(
            rf"\b{product_re}\b.{{0,100}}?(\d{{1,3}}(?:[.,]\d{{3}})*(?:[,.]\d+)?)\s*(?:CVE|Esc|ESC)(?:\s*/\s*(Kg|KG|kg|L|l))?",
            re.IGNORECASE,
        )
        for match in pattern.finditer(text):
            price = _parse_number(match.group(1))
            if price is None:
                continue
            unit_raw = (match.group(2) or "").lower()
            unit = "kg" if unit_raw == "kg" or label == "Gás Butano" else "L"
            if label not in seen:
                out.append((label, price, unit))
                seen.add(label)
            break
    return out


def fetch_arme_cv(cutoff: date) -> pd.DataFrame | None:
    session = make_session()
    rows: list[dict] = []
    for obs_date, article_url in _discover_articles(session):
        if obs_date <= cutoff:
            continue
        try:
            resp = session.get(article_url, timeout=45)
        except Exception:
            logger.exception("[arme_cv] article fetch failed: %s", article_url)
            continue
        if resp.status_code != 200:
            continue
        text = _clean_text(resp.text)
        prices = _parse_prices(text)
        if not prices:
            logger.warning("[arme_cv] no prices parsed: %s", article_url)
            continue
        for label, price, unit in prices:
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
        logger.info("[arme_cv] %s → %d products", obs_date, len(prices))
        time.sleep(_THROTTLE_S)

    if not rows:
        logger.info("[arme_cv] no rows after cutoff %s", cutoff)
        return None
    df = (
        pd.DataFrame(rows)
        .drop_duplicates(subset=["observation_date", "fuel_product"])
        .sort_values(["observation_date", "fuel_product"])
        .reset_index(drop=True)
    )
    logger.info(
        "[arme_cv] %d rows (%s → %s)",
        len(df),
        df["observation_date"].iloc[0],
        df["observation_date"].iloc[-1],
    )
    return df


__all__ = ["fetch_arme_cv"]
