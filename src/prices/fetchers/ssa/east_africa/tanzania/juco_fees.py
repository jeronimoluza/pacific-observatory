"""Jordan University College (JUCo) -- tertiary tuition & fees schedule.

Constituent college of St. Augustine University of Tanzania, Morogoro.
juco.ac.tz publishes six "Fee Structure" PDFs under
https://juco.ac.tz/index.php/fee_structure -- one per programme level
(Certificate, Diploma, Bachelor Degree, Postgraduate Diploma, Master's,
PhD) -- each a clean, machine-readable pdfplumber-extractable table:

    Programme(s): BAED, BASO, BAECO, BAEDRS, BSCPC, BLRIM & BSCCS
    SN Item Name Amount (TZS) Status Currency
    1 Administrative fees 395,000.00 Mandatory TZS
    2 TCU QA Fee 20,000.00 Mandatory TZS
    3 JUCSO Fee 20,000.00 Mandatory TZS
    4 Tuition Fee 1,280,000.00 Mandatory TZS
    TOTAL MANDATORY FEES 1,715,000.00 TZS

The Bachelor Degree PDF repeats this block once per programme group (one
"Programme(s):" header + a 4-line fee table) across its 8 pages; the other
five PDFs (Certificate/Diploma/Postgraduate Diploma/Master's/PhD) use a
single-line "Programme:" header instead of "Programme(s):" and carry one
programme group per document. Both header spellings are parsed by the same
regex. Confirmed live 2026-09-28, Academic Year 2026/2027, "Posted on
2026-09-08" per the fee-structure listing page.

FIRST-YEAR RATES ONLY: every table is headed "ACADEMIC YEAR FEE STRUCTURE
-- FIRST YEAR (2026/2027)" (or "Class: First Year[ & Second Year]" on the
single-block PDFs) -- this fetcher emits the first-year annual mandatory
fee lines only, not the semester installment breakdown that follows each
table (those are arithmetic splits of the same annual total, same
reasoning as comfsm_tuition.py dropping the multiple-of-base-rate rows).

Known source quirk: the Certificate and Diploma PDFs mis-number their SN
column (two rows both labelled "4": "JUCSO Fee" and "NACTVET Verification
fees") -- harmless here since rows are identified by item_name, not SN.

COICOP: all fee lines (administrative, TCU QA, JUCSO, NACTVET
verification, tuition) filed under 10.4.0 (tertiary education services
and compulsory institutional fees) -- JUCo is a single tertiary
institution; certificate-through-PhD programmes are all post-secondary
tertiary provision in COICOP-2018 terms, so no per-level split is applied.

Single-institution source (rule-19 narrow): 21 programme-group fee blocks
across the 6 PDFs on the 2026-09-28 verification run, all TZS, all
mandatory-fee totals in the hundreds-of-thousands to low-millions range
(260,000 -- 4,165,000 TZS), consistent with the docstring's own "TOTAL"
lines. This is one university's published schedule, not a national
average -- complements (does not replace) a future national fee-survey
source per the onboarding brief's institutional-vertical guidance.
"""

import logging
import re
from datetime import date
from io import BytesIO

import pandas as pd
import pdfplumber
from curl_cffi import requests as curl_requests

from prices.fetchers.utils import get_scrape_ts, make_hash

logger = logging.getLogger(__name__)

_LISTING_URL = "https://juco.ac.tz/index.php/fee_structure"
_COUNTRY = "Tanzania"
_CURRENCY = "TZS"
_SOURCE_KEY = "tz_juco_fees"
_UNIT = "TZS/academic_year_1"
_IDENT = ["source_key", "observation_date", "item_name"]
_EDUCATION_COICOP = "10.4.0"

_DOC_BASE = "https://juco.ac.tz/jslabtec/documents/"
_PDF_SOURCES = [
    ("Certificate", _DOC_BASE + "Certificate programmes fee structure - 2026-2027.pdf"),
    ("Diploma", _DOC_BASE + "Diploma Programmes fee structure - 2026-2027.pdf"),
    ("Bachelor Degree", _DOC_BASE + "Bachelor Deree Prommes fee structure - 2026-2027.pdf"),
    ("Postgraduate Diploma", _DOC_BASE + "Postraduate Diploma fee structure - 2026-2027.pdf"),
    ("Master's", _DOC_BASE + "Masters programmes fee structue - 2026-2027.pdf"),
    ("PhD", _DOC_BASE + "PhD Programmes fee structure - 2026-2027.pdf"),
]

_PROGRAMME_RE = re.compile(r"^Programme\(?s?\)?:\s*(.+)$")
_ITEM_RE = re.compile(r"^\d+\s+(.+?)\s+([\d,]+\.\d{2})\s+(\S+)\s+TZS$")


def _parse_pdf(level: str, content: bytes) -> list[dict]:
    with pdfplumber.open(BytesIO(content)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    programme = None
    items: list[dict] = []
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        m_prog = _PROGRAMME_RE.match(line)
        if m_prog:
            programme = m_prog.group(1).strip()
            continue
        m_item = _ITEM_RE.match(line)
        if not m_item or programme is None:
            continue
        fee_name, amount_text, status = m_item.groups()
        if status.lower() != "mandatory":
            continue  # optional/non-mandatory lines are not a price observation
        try:
            amount = float(amount_text.replace(",", ""))
        except ValueError:
            continue
        if amount <= 0:
            continue
        items.append(
            {
                "item_name": f"{level} -- {programme} -- {fee_name.strip()}",
                "price_local": amount,
            }
        )
    return items


def fetch_tz_juco_fees(cutoff: date) -> pd.DataFrame | None:
    today = date.today()
    if today <= cutoff:
        logger.info("[%s] already snapshotted today (cutoff=%s)", _SOURCE_KEY, cutoff)
        return None

    all_items: list[dict] = []
    for level, url in _PDF_SOURCES:
        try:
            resp = curl_requests.get(url, impersonate="chrome124", timeout=30)
            resp.raise_for_status()
        except Exception:
            logger.warning("[%s] failed to fetch %s", _SOURCE_KEY, url, exc_info=True)
            continue
        parsed = _parse_pdf(level, resp.content)
        if not parsed:
            logger.warning("[%s] no fee rows parsed from %s", _SOURCE_KEY, url)
            continue
        all_items.extend(parsed)

    if not all_items:
        logger.warning("[%s] no fee rows parsed from any document", _SOURCE_KEY)
        return None

    ts = get_scrape_ts()
    rows = []
    for item in all_items:
        row = {
            "observation_date": today.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "subnational_area": None,
            "source_key": _SOURCE_KEY,
            "coicop_code": _EDUCATION_COICOP,
            "item_name": item["item_name"],
            "price_local": item["price_local"],
            "currency": _CURRENCY,
            "unit": _UNIT,
            "source_url": _LISTING_URL,
            "notes": None,
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows)
