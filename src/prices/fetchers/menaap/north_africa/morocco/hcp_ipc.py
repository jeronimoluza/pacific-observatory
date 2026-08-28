"""Morocco HCP (Haut-Commissariat au Plan) — Consumer Price Index, monthly, DOCX note.

HCP (hcp.ma) publishes a monthly "Note d'information ... relative a l'Indice des
prix a la consommation (IPC)" as a Word (.docx) attachment linked from a page at
/L-Indice-des-prix-a-la-consommation-IPC-du-mois-de-<Month>-<Year>_a<id>.html
(the numeric page id is not predictable from the month/year, so the current
release is discovered via the link on hcp.ma's own homepage each run).
Re-verified live 2026-08-07: homepage links the Juin-2026 note -> 200,
attachment (docx, ~75KB) contains a table "EVOLUTION PAR DIVISION DE PRODUITS"
with month-over-month index levels for all 12 COICOP-style product divisions
(01-12), comparing Mai 2026 and Juin 2026 -- genuinely current, not stale.

Unlike Jordan's DOS CPI / Tunisia's INS IPC (both onboarded earlier this shard),
each HCP note carries only TWO monthly data points (current + previous month),
not a cumulative time series -- so this fetcher is a real-time walker, not a
one-shot backfill. `fallback_date` is set close to today so the first run's
result matches what is actually retrievable (the two months in the current
note), not an implied deeper history this source shape cannot provide.
Ongoing monthly `prices collect` runs accumulate history one month at a time
(each note's "previous month" column overlaps the prior run's "current month",
so no gap even if a run is skipped once).

Only the division-level table is parsed -- HCP's note does not break out
COICOP groups/classes, only the 12 top-level divisions, each already labeled
with its own 2-digit code by the publisher (e.g. "01 - Produits alimentaires
et boissons non alcoolisees"), so coicop_code is a direct passthrough of the
regex-captured division number -- no translation map needed. The "Produits
alimentaires" / "Produits non alimentaires" subtotal rows and the "Ensemble"
(all-items) row are intentionally not captured by the division-row regex
(it only matches "NN - <label>" prefixed rows) -- correctly excluded, same as
the all-items drop in the other two CPI fetchers in this shard.

index_base_period is left as "not stated in source note" -- HCP's monthly
note does not restate the IPC base year (unlike Jordan/Tunisia's tables,
which carry it in the title), and it was not independently confirmed via
a methodology page during this onboarding pass. Do not backfill this with an
assumed year without checking hcp.ma's IPC methodology documentation first.

analytical_role: cpi_benchmark -> IndexObservation, not PriceObservation.
coicop_classification: publisher_labeled (direct numeric division code from
the publisher, no string-label translation needed).
coicop_divisions: 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12
"""

from __future__ import annotations

import logging
import re
import zipfile
from datetime import date
from io import BytesIO

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Morocco"
_SOURCE_KEY = "ma_hcp_ipc"
_HOME_URL = "https://www.hcp.ma/"
_IDENT = ["source_key", "observation_date", "coicop_code"]

_RELEASE_LINK_RE = re.compile(
    r'href="(/L-Indice-des-prix-a-la-consommation-IPC-du-mois-de-[^"]+\.html)"'
)
_ATTACHMENT_RE = re.compile(r'href="(https://www\.hcp\.ma/attachment/\d+/)"')
_DIVISION_ROW_RE = re.compile(
    r"(0[1-9]|1[0-2]) - (.+?)(\d{2,3},\d)(\d{2,3},\d)(-?\d+,\d)"
)
_HEADER_RE = re.compile(r"Indices mensuels(\D*?)(\d{4})(\D*?)(\d{4})Var")

_FR_MONTHS = {
    "janvier": 1,
    "février": 2,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "août": 8,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "décembre": 12,
    "decembre": 12,
}


def _fr_num(s: str) -> float:
    return float(s.replace(",", "."))


def _find_latest_release_url(session) -> str | None:
    try:
        r = session.get(_HOME_URL, timeout=30)
        r.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] homepage fetch failed: %s", _SOURCE_KEY, exc)
        return None
    m = _RELEASE_LINK_RE.search(r.text)
    if not m:
        logger.warning("[%s] no IPC release link found on homepage", _SOURCE_KEY)
        return None
    return "https://www.hcp.ma" + m.group(1)


def _find_docx_url(session, page_url: str) -> str | None:
    try:
        r = session.get(page_url, timeout=30)
        r.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] release page fetch failed: %s", _SOURCE_KEY, exc)
        return None
    m = _ATTACHMENT_RE.search(r.text)
    return m.group(1) if m else None


def _docx_text(docx_bytes: bytes) -> str:
    z = zipfile.ZipFile(BytesIO(docx_bytes))
    xml = z.read("word/document.xml").decode("utf-8")
    text = re.sub(r"<[^>]+>", "", xml)
    return re.sub(r"\s+", " ", text)


def _rows_from_note(text: str, source_url: str, cutoff: date) -> list[dict]:
    start = text.find("Indices mensuels")
    end = text.find("Source :", start) if start >= 0 else -1
    if start < 0 or end < 0:
        return []
    block = text[start:end]

    hdr = _HEADER_RE.search(block)
    if not hdr:
        return []
    m1_name, y1, m2_name, y2 = hdr.groups()
    m1 = _FR_MONTHS.get(m1_name.strip().lower())
    m2 = _FR_MONTHS.get(m2_name.strip().lower())
    if not m1 or not m2:
        logger.warning(
            "[%s] unrecognized month names %r/%r", _SOURCE_KEY, m1_name, m2_name
        )
        return []
    date1 = date(int(y1), m1, 1)
    date2 = date(int(y2), m2, 1)

    ts = get_scrape_ts()
    rows: list[dict] = []
    for code, _label, val1, val2, _var in _DIVISION_ROW_RE.findall(block):
        for obs_date, raw_val in ((date1, val1), (date2, val2)):
            if obs_date <= cutoff:
                continue
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "monthly_avg",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": code,
                "index_value": _fr_num(raw_val),
                "index_base_period": "not stated in source note",
                "source_url": source_url,
                "scrape_ts": ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)
    return rows


def fetch_ma_hcp_ipc(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    release_url = _find_latest_release_url(session)
    if not release_url:
        return None
    docx_url = _find_docx_url(session, release_url)
    if not docx_url:
        logger.warning("[%s] no docx attachment found on %s", _SOURCE_KEY, release_url)
        return None
    try:
        resp = session.get(docx_url, timeout=60)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] docx fetch failed: %s", _SOURCE_KEY, exc)
        return None

    text = _docx_text(resp.content)
    rows = _rows_from_note(text, release_url, cutoff)
    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
