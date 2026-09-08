"""Macao SAR -- University of Macau (UM) undergraduate tuition fee schedule,
snapshot.

UM's public "Fees" page (um.edu.mo/study/fees/) is just an index of links
into a single registrar page (reg.um.edu.mo/.../tuition-and-other-fees-and-
charges/) that holds ALL fee schedules in one long page. Each fee schedule
is a genuinely tabular (not scanned) HTML table with clean "Student Type"
-> "MOP" columns, so no PDF is needed for this source (the Bachelor's PDF
linked on-page is just a formatted export of the same figures).

IMPORTANT parsing gotcha found during onboarding: the page's `id="<hash>"`
anchors do NOT mark the start of their section's content -- they sit near
the END of a section (confirmed by byte-offset: the "Minor Programme"
anchor position is AFTER its own per-credit fee table, which instead sits
inside byte-range that "looks like" the Bachelor's section). Slicing the
raw HTML by anchor position and re-parsing each fragment with
`pandas.read_html` therefore attributes tables to the WRONG heading --
caught by cross-checking the surrounding sentence text ("graduation of the
Minor Programme" / "... Honours College Certificate Programme"), which
does NOT move around with slicing. The safe approach used here instead:
run `pandas.read_html` ONCE on the whole page (preserves true document
order) and select tables by their COLUMN HEADER signature, taking the
FIRST match of each signature -- "Programme Type"+"Student Type" for
Bachelor's, "per Credit" for the Minor Programme, "Programme Full Tuition
Fee#" for Honours College. A fourth table sharing that exact same last
signature exists FURTHER DOWN the page (confirmed unrelated -- it sits
under an "Other Fees and Charges" / "AY2025/2026" heading, not Honours
College) and is correctly skipped because only the first match is kept.

Rows are Local vs Non-local Students (UM, like most Macao institutions,
charges non-local students several times the local rate):
    Bachelor's (4yr): Local 150,000 / Non-local 490,400 MOP (full programme)
    Bachelor's (5yr): Local 187,500 / Non-local 613,000 MOP (full programme)
    Minor Programme: Local 1,150 / Non-local 3,850 MOP (per credit)
    Honours College Certificate: Local 20,940 / Non-local 69,900 MOP (full programme)

"Full programme" fees (Bachelor's, Honours) are converted to a per-year
figure using the programme's own stated duration (4 or 5 years for
Bachelor's; Honours College is a bolt-on certificate typically completed
alongside a 4-year degree, so divided by 4) so all rows share a comparable
`unit: year` -- except the Minor Programme row, which the source itself
prices per credit (`unit: credit`), left as-is rather than invented into a
per-year figure with no stated credit load.

No effective-date field was found on the page itself; the linked PDF's own
filename ("...-2627-...") indicates the 2026/2027 academic year, so
effective_from is set to the academic year's start (2026-09-01) as a
best-effort estimate, recorded as such rather than silently guessed.

Currency: MOP, matches countries.yaml. coicop_classification:
source_curated -- COICOP 10.4.0.0 (tertiary education).
"""

from __future__ import annotations

import logging
from datetime import date
from io import StringIO

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_PAGE_URL = "https://reg.um.edu.mo/current-students/enrolment-and-examinations/tuition-and-other-fees-and-charges/"
_COUNTRY = "Macao SAR, China"
_CURRENCY = "MOP"
_SOURCE_KEY = "mo_um_tuition_fees"
_COICOP_CODE = "10.4.0.0"
_IDENT = ["source_key", "observation_date", "item_name"]
_EFFECTIVE_FROM = date(2026, 9, 1)  # 2026/2027 academic year, best-effort estimate

_SIGNATURES = [
    ("Bachelor's Degree Programme", lambda cols: any("Programme Type" in c for c in cols) and any("Student Type" in c for c in cols)),
    ("Minor Programme", lambda cols: any("per Credit" in c for c in cols)),
    (
        "Honours College Certificate Programme",
        lambda cols: any("Programme Full Tuition Fee" in c for c in cols)
        and not any("Programme Type" in c for c in cols),
    ),
]


def fetch_mo_um_tuition_fees(cutoff: date) -> pd.DataFrame | None:
    if _EFFECTIVE_FROM <= cutoff:
        logger.info("[%s] no new release past cutoff=%s", _SOURCE_KEY, cutoff)
        return None

    session = get_session()
    try:
        resp = session.get(_PAGE_URL, timeout=60)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] page fetch failed: %s", _SOURCE_KEY, exc)
        return None

    try:
        tables = pd.read_html(StringIO(resp.text))
    except ValueError as exc:
        logger.warning("[%s] no HTML tables found: %s", _SOURCE_KEY, exc)
        return None

    parsed: list[dict] = []
    for label, matcher in _SIGNATURES:
        cols_by_table = [[str(c) for c in tbl.columns] for tbl in tables]
        tbl = next(
            (tbl for tbl, cols in zip(tables, cols_by_table) if matcher(cols)),
            None,
        )
        if tbl is None:
            logger.warning("[%s] no fee table found for section %r", _SOURCE_KEY, label)
            continue
        fee_col = next(c for c in tbl.columns if "MOP" in str(c) or "Fee" in str(c))
        for _, row in tbl.iterrows():
            try:
                fee = float(row[fee_col])
            except (ValueError, TypeError):
                continue
            if fee <= 0:
                continue
            student_type = str(row.get("Student Type", "")).strip()
            programme_type = str(row.get("Programme Type", "")).strip()
            name_parts = [label]
            if programme_type and programme_type.lower() != "nan":
                name_parts.append(programme_type)
            if student_type and student_type.lower() != "nan":
                name_parts.append(student_type)
            item_name = ", ".join(name_parts)

            if label == "Minor Programme":
                unit = "credit"
                price = fee
            else:
                # full-programme fee -> per-year; duration comes from the
                # programme_type text ("4-year"/"5-year") when present,
                # else Honours College bolts onto a 4-year degree.
                years = 4
                if "5-year" in programme_type:
                    years = 5
                unit = "year"
                price = round(fee / years, 2)

            parsed.append({"item_name": item_name[:200], "price_local": price, "unit": unit})

    if not parsed:
        logger.warning("[%s] no fee rows parsed from %s", _SOURCE_KEY, _PAGE_URL)
        return None

    ts = get_scrape_ts()
    rows: list[dict] = []
    for p in parsed:
        row = {
            "observation_date": _EFFECTIVE_FROM.isoformat(),
            "period_kind": "effective_from",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP_CODE,
            "item_name": p["item_name"],
            "price_local": p["price_local"],
            "currency": _CURRENCY,
            "unit": p["unit"],
            "source_url": _PAGE_URL,
            "notes": "UM undergraduate tuition; full-programme fees converted to per-year using stated duration",
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
