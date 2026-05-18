"""NBS Nigeria — National Bureau of Statistics monthly Price Watch series.

NBS publishes three parallel monthly retail-price PDFs in its e-library:

* Premium Motor Spirit (PMS) Price Watch    — gasoline, NGN/litre
* Automotive Gas Oil (AGO) Price Watch      — diesel, NGN/litre
* National Household Kerosene Price Watch   — kerosene, NGN/litre

The e-library index at ``/elibrary`` server-renders the entire catalog as
HTML rows (no pagination needed). Each ``<tr>`` carries the publication
title and a button linking ``/elibrary/read/<id>``; ``<id>`` is reused for
``/download/<id>`` which returns the PDF directly. We parse rows, filter by
series title, derive the data month from the title, then fetch each PDF.

The state-level table (36 states + FCT) lives in the appendix as lines
    <state> <ya-price> <prev-month> <current-month> <MoM%> <YoY%>
We use pdfplumber's text extractor (rather than table extractor — HHK
tables come back malformed) and keep the FIRST occurrence per state; HHK
prints LITRE before GALLON, which is the figure we want.
"""

import io
import logging
import re
import time
from datetime import date
from urllib.parse import urljoin

import pandas as pd

from core.http import make_session

logger = logging.getLogger(__name__)

_BASE_URL = "https://nigerianstat.gov.ng"
_INDEX_PATH = "/elibrary"
_COUNTRY = "Nigeria"
_CURRENCY = "NGN"
_SOURCE_KEY = "nbs_ng_state_monthly"

_THROTTLE_S = 1.5

# series_match_keyword (lower-case substring) → fuel_product (YAML key)
_SERIES = (
    ("premium motor spirit", "PMS"),
    ("automotive gas oil", "AGO"),
    ("automative gas oil", "AGO"),  # NBS sometimes misspells "Automative"
    ("national household kerosene", "HHK"),
    ("household kerosene", "HHK"),
)

# Skip "Liquefied Petroleum Gas" deliberately — per-kg, different ProductSpec.

# Catalog row: each <tr> has the title in the first visible <td> and a
# button linking ``/elibrary/read/<id>``. Captures (title, id).
_ROW_RE = re.compile(
    r"<tr>\s*(?:<!--.*?-->)?\s*<td>([^<]+)</td>" r".*?/elibrary/read/(\d+)",
    re.DOTALL | re.IGNORECASE,
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
}
_MONTH_YEAR_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\s+(\d{4})\b",
    re.IGNORECASE,
)

# Nigeria's 36 states + FCT. Zone-header rows ("NORTH CENTRAL" etc.) are
# upper-case and won't match this set — they get skipped.
_STATES = {
    "Abia",
    "Adamawa",
    "Akwa Ibom",
    "Anambra",
    "Bauchi",
    "Bayelsa",
    "Benue",
    "Borno",
    "Cross River",
    "Delta",
    "Ebonyi",
    "Edo",
    "Ekiti",
    "Enugu",
    "Gombe",
    "Imo",
    "Jigawa",
    "Kaduna",
    "Kano",
    "Katsina",
    "Kebbi",
    "Kogi",
    "Kwara",
    "Lagos",
    "Nasarawa",
    "Niger",
    "Ogun",
    "Ondo",
    "Osun",
    "Oyo",
    "Plateau",
    "Rivers",
    "Sokoto",
    "Taraba",
    "Yobe",
    "Zamfara",
    "Abuja",
    "FCT",
    "FCT Abuja",
    "Abuja FCT",
}


def _parse_title_month(title: str) -> date | None:
    m = _MONTH_YEAR_RE.search(title)
    if not m:
        return None
    month = _MONTHS.get(m.group(1).lower())
    if not month:
        return None
    try:
        return date(int(m.group(2)), month, 1)
    except ValueError:
        return None


def _parse_price(raw: object) -> float | None:
    if raw is None:
        return None
    text = str(raw).strip().replace(",", "")
    if not text or text in {"-", "—", "N/A"}:
        return None
    try:
        val = float(text)
    except ValueError:
        return None
    return val if val > 0 else None


def _classify_title(title: str) -> str | None:
    """Return product code (PMS/AGO/HHK) for a publication title, or None."""
    lowered = title.lower()
    for keyword, code in _SERIES:
        if keyword in lowered:
            return code
    return None


def _discover_all(
    session,
    cutoff: date,
) -> list[tuple[int, date, str, str]]:
    """Walk the e-library catalog once and return all matching publications.

    Returns sorted list of (pub_id, effective_date, product_code, title).
    """
    url = f"{_BASE_URL}{_INDEX_PATH}"
    resp = session.get(url, timeout=60)
    resp.raise_for_status()
    html = resp.text

    out: list[tuple[int, date, str, str]] = []
    seen: set[int] = set()
    for match in _ROW_RE.finditer(html):
        title = re.sub(r"\s+", " ", match.group(1)).strip()
        pub_id = int(match.group(2))
        if pub_id in seen:
            continue
        seen.add(pub_id)
        code = _classify_title(title)
        if code is None:
            continue
        obs_date = _parse_title_month(title)
        if obs_date is None:
            continue
        if obs_date <= cutoff:
            continue
        out.append((pub_id, obs_date, code, title))
    logger.info(
        "[nbs_ng] catalog: %d rows scanned, %d matching pubs after cutoff %s",
        len(seen),
        len(out),
        cutoff,
    )
    return sorted(out, key=lambda x: (x[1], x[2]))


def _download_pdf(session, pub_id: int) -> bytes | None:
    url = urljoin(_BASE_URL, f"/download/{pub_id}")
    try:
        resp = session.get(url, timeout=90)
    except Exception:
        logger.exception("[nbs_ng] download %s failed", url)
        return None
    if resp.status_code != 200 or resp.content[:4] != b"%PDF":
        logger.warning("[nbs_ng] %s → not a PDF (HTTP %d)", url, resp.status_code)
        return None
    return resp.content


_STATE_LINE_RE = re.compile(
    r"^(" + "|".join(sorted(_STATES, key=len, reverse=True)) + r")"
    r"\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)",
    re.MULTILINE,
)


def _extract_state_prices(pdf_bytes: bytes) -> dict[str, float]:
    """Return {state: current_month_price} via text-extraction."""
    try:
        import pdfplumber
    except ImportError:
        logger.error("[nbs_ng] pdfplumber not installed")
        return {}

    out: dict[str, float] = {}
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                for m in _STATE_LINE_RE.finditer(text):
                    state = m.group(1)
                    # State row has 3 captured numbers: year-ago, prev-month,
                    # current-month. Take current-month (group 4).
                    price = _parse_price(m.group(4))
                    if price is None:
                        continue
                    out.setdefault(state, price)
    except Exception:
        logger.exception("[nbs_ng] PDF text parse failed")
    return out


def fetch_nbs_ng(cutoff: date) -> pd.DataFrame | None:
    session = make_session()

    pubs = _discover_all(session, cutoff)
    if not pubs:
        logger.info("[nbs_ng] No publications after cutoff %s", cutoff)
        return None

    all_rows: list[dict] = []
    for pub_id, obs_date, product_code, title in pubs:
        time.sleep(_THROTTLE_S)
        pdf_bytes = _download_pdf(session, pub_id)
        if pdf_bytes is None:
            continue
        state_prices = _extract_state_prices(pdf_bytes)
        if not state_prices:
            logger.warning(
                "[nbs_ng] %s/%s id=%d → no state table found",
                product_code,
                obs_date,
                pub_id,
            )
            continue
        iso = obs_date.strftime("%Y-%m-%d")
        for state, price in state_prices.items():
            all_rows.append(
                {
                    "observation_date": iso,
                    "country": _COUNTRY,
                    "fuel_product": product_code,
                    "price_local": price,
                    "currency": _CURRENCY,
                    "unit": "L",
                    "source_key": _SOURCE_KEY,
                    "city": state,
                }
            )
        logger.info(
            "[nbs_ng] %s id=%d %s → %d states",
            product_code,
            pub_id,
            obs_date,
            len(state_prices),
        )

    if not all_rows:
        logger.info("[nbs_ng] No rows produced for cutoff %s", cutoff)
        return None

    df = (
        pd.DataFrame(all_rows)
        .drop_duplicates(subset=["observation_date", "city", "fuel_product"])
        .sort_values(["observation_date", "fuel_product", "city"])
        .reset_index(drop=True)
    )
    logger.info(
        "[nbs_ng] %d total rows (%s → %s, %d products)",
        len(df),
        df["observation_date"].iloc[0],
        df["observation_date"].iloc[-1],
        df["fuel_product"].nunique(),
    )
    return df


__all__ = ["fetch_nbs_ng"]
