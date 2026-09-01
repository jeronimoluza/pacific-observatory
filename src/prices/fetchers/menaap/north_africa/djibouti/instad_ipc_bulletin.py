"""INSTAD (Institut National de la Statistique de Djibouti) -- monthly IPC bulletin,
"Tableau 4: Prix moyen des produits de première nécessité" (average price of
essential/staple products), a national-average retail price-level table --
distinct from the CPI index values published alongside it in the same PDF.

Discovery: instad.dj is a Nuxt 3 SPA (client-side rendered, no prerendered
routes -- confirmed via /_nuxt/builds/meta/<buildId>.json returning an empty
"prerendered": []). The bot-detectable path is a dead end for scraping the
site's own pages. Sniffing the browser's network calls (Playwright, one-off,
not part of runtime) while loading /indice/ipc revealed the real backend: a
Node/Express API at instad-dj-6abc7b0eb612.herokuapp.com backing a document
library. GET
  /fichiers/Indice%20des%20prix%20%C3%A0%20la%20consommation/<year>
returns a plain JSON array of monthly bulletin records (title, year, 0-indexed
month, imgUrl -> the bulletin PDF on Firebase Storage). No auth, no WAF; both
endpoints work with a bare `requests` session (no curl_cffi impersonation
needed -- verified live 2026-08-31).

Each monthly PDF's Tableau 4 lists ~29 staple items (rice, pasta, meat,
vegetables, milk, sugar, flour, cooking oil, plus three retail fuel grades
GAZOIL/SUPER/KEROZENE) with a *rolling 6-month* price history in FDJ (the
national currency, ISO DJF) -- e.g. header row "Fév-26 Mars-26 Avr-26 Mai-26
Juin-26 Juil-26" for the July 2026 release. One row is emitted per
(item, month) cell, so a single bulletin backfills 6 months of history;
month-over-month re-runs naturally re-assert the same observation_hash for
the overlapping 5 months and only the newest month is new (verified: the
downstream writer dedups on observation_hash).

Table 3 (the COICOP-division CPI index, same PDF) is NOT parsed here --
its month header row is pdfplumber-mangled by rotated column headers
("Janv- Oct- Nov- Déc- Janv-" with the digits detached) and it's an index
series, not a price-level series; a future cpi_benchmark manifest can
revisit it separately per onboarding doctrine.

Verified 2026-08-31 against the July 2026 release (2026, month=6): 29 items x
6 columns = 174 candidate rows.
"""

from __future__ import annotations

import io
import logging
import re
import unicodedata
from datetime import date

import pandas as pd
import pdfplumber

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_API_BASE = "https://instad-dj-6abc7b0eb612.herokuapp.com/fichiers/"
_CATEGORY = "Indice des prix à la consommation"
_COUNTRY = "Djibouti"
_SOURCE_KEY = "instad_ipc_dji"
_CURRENCY = "DJF"
_IDENT = ["source_key", "observation_date", "item_name"]

_MONTH_NUM = {
    "janv": 1,
    "jan": 1,
    "fev": 2,
    "mars": 3,
    "avr": 4,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juil": 7,
    "juillet": 7,
    "aout": 8,
    "sept": 9,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

_HEADER_TOKEN_RE = re.compile(r"([A-Za-zÀ-ÿ]+)-(\d{2})")
_NUM_TOKEN_RE = re.compile(r"^-?\d+(?:[.,]\d+)?$")
_TABLE4_START_RE = re.compile(
    r"Tableau\s*4\s*:\s*Prix moyen des produits de première nécessité", re.IGNORECASE
)


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    )


def _month_num(token: str) -> int | None:
    return _MONTH_NUM.get(_strip_accents(token).lower())


def _list_bulletins(session, year: int) -> list[dict]:
    url = f"{_API_BASE}{_CATEGORY}/{year}"
    try:
        r = session.get(url, timeout=30)
        r.raise_for_status()
        data = r.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] listing fetch failed for %d: %s", _SOURCE_KEY, year, exc)
        return []
    return [
        d
        for d in data
        if isinstance(d, dict)
        and str(d.get("imgUrl", "")).lower().split("?")[0].endswith(".pdf")
    ]


def _latest_bulletin(session) -> dict | None:
    this_year = date.today().year
    candidates = _list_bulletins(session, this_year) + _list_bulletins(
        session, this_year - 1
    )
    if not candidates:
        return None
    return max(
        candidates, key=lambda d: (int(d.get("year", 0)), int(d.get("month", -1)))
    )


def _extract_text(pdf_bytes: bytes) -> str:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages)


def _parse_table4(text: str) -> tuple[list[date], list[tuple[str, list[float]]]]:
    start_m = _TABLE4_START_RE.search(text)
    if not start_m:
        return [], []
    # The title line continues past the match (e.g. "... au mois de juillet
    # 2026.") on the same line before the real header row starts; skip to
    # the next newline so the header parse below sees the header row first.
    title_nl = text.find("\n", start_m.end())
    block = text[title_nl + 1 :] if title_nl != -1 else text[start_m.end() :]
    end_m = re.search(r"Source\s*:\s*INSTAD", block)
    if end_m:
        block = block[: end_m.start()]

    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    if not lines:
        return [], []

    # First line is the 6-column month/year header, e.g. "Fév-26 Mars-26 ..."
    header_matches = _HEADER_TOKEN_RE.findall(lines[0])
    col_dates: list[date] = []
    for month_tok, yy in header_matches:
        month = _month_num(month_tok)
        if month is None:
            continue
        col_dates.append(date(2000 + int(yy), month, 1))
    if len(col_dates) != 6:
        logger.warning(
            "[%s] Table 4 header parsed %d/6 columns from %r",
            _SOURCE_KEY,
            len(col_dates),
            lines[0],
        )
        return [], []

    rows: list[tuple[str, list[float]]] = []
    for line in lines[1:]:
        tokens = line.split()
        if len(tokens) < 7:
            continue
        tail = tokens[-6:]
        if not all(_NUM_TOKEN_RE.match(t) for t in tail):
            continue
        name = " ".join(tokens[:-6]).strip()
        if not name:
            continue
        values = [float(t.replace(",", ".")) for t in tail]
        rows.append((name, values))

    return col_dates, rows


def fetch_instad_ipc_dji(cutoff: date) -> pd.DataFrame | None:
    session = get_session()

    bulletin = _latest_bulletin(session)
    if not bulletin:
        logger.warning("[%s] no bulletin found", _SOURCE_KEY)
        return None

    pdf_url = bulletin["imgUrl"]
    try:
        resp = session.get(pdf_url, timeout=60)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] PDF fetch failed (%s): %s", _SOURCE_KEY, pdf_url, exc)
        return None

    text = _extract_text(resp.content)
    col_dates, table_rows = _parse_table4(text)
    if not table_rows:
        logger.warning("[%s] no Table 4 rows parsed from %s", _SOURCE_KEY, pdf_url)
        return None

    ts = get_scrape_ts()
    title = str(bulletin.get("title") or "Bulletin IPC").strip()
    out: list[dict] = []
    for item_name, values in table_rows:
        for obs_date, price in zip(col_dates, values):
            if obs_date <= cutoff:
                continue
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "monthly",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "item_name": item_name,
                "price_local": price,
                "currency": _CURRENCY,
                "unit": None,
                "source_url": pdf_url,
                "notes": f"{title}; Tableau 4 national average price of staple products",
                "scrape_ts": ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            out.append(row)

    logger.info(
        "[%s] %d new rows from %s (cutoff=%s)", _SOURCE_KEY, len(out), pdf_url, cutoff
    )
    return pd.DataFrame(out) if out else None
