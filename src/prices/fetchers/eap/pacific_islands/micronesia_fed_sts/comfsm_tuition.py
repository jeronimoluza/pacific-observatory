"""College of Micronesia-FSM (COM-FSM) -- tuition and fees schedule.

comfsm.fm publishes the Department of Student Services "tuition fees" page
(``/national/administration/VPSS/tuitionfees.html``) as a series of plain
server-rendered HTML ``<table>``s, one per fee category, each identified
here by a stable label cell rather than table position (the page's table
count shifts as unrelated program-listing tables are added/removed above
the fee tables).

Fee groups extracted:

- **Tuition** -- only the base "1 credit" rate ($95.00/credit) is emitted.
  The page also tabulates the same rate x {3,6,9,12,15,18} credits; those
  are arithmetic multiples of the single per-credit rate, not independent
  observations, so they are not re-emitted (same reasoning as
  ``puc_tariff.py`` dropping the derived senior-discount delta).
- **Dormitory** -- Regular Semester / Summer Session flat fees.
- **Meals (Board)** -- Regular Semester and Summer Session, each split
  on-campus / off-campus, plus per-meal Daily Rate (breakfast, lunch-or-
  dinner).
- **Enrollment / admin fees** -- Entrance Test, Admission, Registration,
  Health, Student Activity, Technology, Laboratory, Late Registration,
  Auditing, Credit-By-Examination, Graduation, Transcript, Duplicate ID,
  Duplicate Diploma, NSF Check.

The "Residence Hall/Dormitory Security Deposit" ($50) is deliberately NOT
emitted -- it is refundable and not an independent price, the same class of
exclusion as the PUC senior-discount line.

COICOP: tuition + admin/enrollment fees are filed under 10.4.0 (tertiary
education services and compulsory institutional fees); dormitory under
11.2.0 (accommodation services); meals under 11.1.1 (catering services).

No reliable single effective-date covers the whole page: the tuition rate
text states "adopted ... December 2006 ... implemented effective Spring
2007", the page footer says "last modified 01/04/2009", and none of the
other fee lines carry a date at all. This is a live page COM-FSM edits in
place, not a dated schedule -- modelled as a daily period_kind=snapshot at
scrape time, same pattern as ``puc_tariff.py``. The rates are visibly stale
(unmoved for ~15+ years per the page's own footer date) -- flagged in the
YAML notes, not silently treated as current-year pricing.

Currency is USD (FSM's actual currency, no FX conversion needed).
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Micronesia, Fed. Sts."
_CURRENCY = "USD"
_SOURCE_KEY = "fm_comfsm_tuition"
_URL = "http://www.comfsm.fm/national/administration/VPSS/tuitionfees.html"
_IDENT = ["source_key", "observation_date", "item_name"]

_EDUCATION_COICOP = "10.4.0"
_ACCOMMODATION_COICOP = "11.2.0"
_CATERING_COICOP = "11.1.1"

_ADMIN_FEE_LABELS = {
    "Entrance Test Fee",
    "Admission Fee",
    "Registration Fee",
    "Health Fee",
    "Student Activity Fee",
    "Technology Fee",
    "Laboratory Fee",
    "Late Registration Fee",
    "Auditing Fee",
    "Credit-By-Examination Fee",
    "Graduation Fee",
    "Transcript Fee",
    "Duplicate ID Fee",
    "Duplicate Diploma Fee",
    "No Sufficient Fund (NSF) Check Fee",
}


def _price(text: str) -> float | None:
    m = re.search(r"[\d,.]+", text.replace(",", ""))
    if not m:
        return None
    try:
        val = float(m.group(0))
    except ValueError:
        return None
    return val if val > 0 else None


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _table_containing(soup: BeautifulSoup, exact_text: str):
    """Return the innermost ``<table>`` holding a ``<td>`` matching exactly.

    Walks ``<td>`` elements directly (not ``soup.find_all("table")``) and
    takes ``find_parent("table")`` off the matching cell. This page's HTML
    has one large malformed outer layout table wrapping the entire fee
    section; under lxml's stricter nesting repair that outer table's own
    ``find_all("td")`` recurses into every nested table and matches almost
    any marker, so scanning top-level tables in document order picks the
    giant wrapper every time instead of the small fee-specific table.
    """
    for td in soup.find_all("td"):
        if _clean(td.get_text(" ", strip=True)) == exact_text:
            return td.find_parent("table")
    return None


def _flat_fee_rows(table) -> list[tuple[str, float]]:
    out = []
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) != 2:
            continue
        label = _clean(cells[0].get_text(" ", strip=True))
        price = _price(cells[1].get_text(" ", strip=True))
        if not label or price is None:
            continue
        out.append((label, price))
    return out


def _parse_meals(table) -> list[dict]:
    out = []
    section = None
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) != 2:
            continue
        label = _clean(cells[0].get_text(" ", strip=True))
        price_text = cells[1].get_text(" ", strip=True)
        if label.endswith(":"):
            section = label.rstrip(":").strip()
            continue
        price = _price(price_text)
        if not label or price is None:
            continue
        unit = "USD/day" if section == "Daily Rate" else "USD/semester"
        item_name = f"Meal -- {section} -- {label}" if section else f"Meal -- {label}"
        out.append(
            {
                "item_name": item_name,
                "price_local": price,
                "unit": unit,
                "coicop_code": _CATERING_COICOP,
            }
        )
    return out


def fetch_fm_comfsm_tuition(cutoff: date) -> pd.DataFrame | None:
    today = date.today()
    if today <= cutoff:
        logger.info("[%s] already snapshotted today (cutoff=%s)", _SOURCE_KEY, cutoff)
        return None

    session = get_session()
    resp = session.get(_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    items: list[dict] = []

    tuition_table = _table_containing(soup, "1 credit")
    if tuition_table is not None:
        tuition = dict(_flat_fee_rows(tuition_table)).get("1 credit")
        if tuition is not None:
            items.append(
                {
                    "item_name": "Tuition -- per credit hour",
                    "price_local": tuition,
                    "unit": "USD/credit",
                    "coicop_code": _EDUCATION_COICOP,
                }
            )
    else:
        logger.warning("[%s] tuition table not found", _SOURCE_KEY)

    dorm_table = _table_containing(soup, "Summer Session")
    if dorm_table is not None:
        for label, price in _flat_fee_rows(dorm_table):
            items.append(
                {
                    "item_name": f"Dormitory -- {label}",
                    "price_local": price,
                    "unit": "USD/semester" if label == "Regular Semester" else "USD/summer session",
                    "coicop_code": _ACCOMMODATION_COICOP,
                }
            )
    else:
        logger.warning("[%s] dormitory fee table not found", _SOURCE_KEY)

    meal_table = _table_containing(soup, "Breakfast")
    if meal_table is not None:
        items += _parse_meals(meal_table)
    else:
        logger.warning("[%s] meal fee table not found", _SOURCE_KEY)

    admin_tables_seen = set()
    for marker in ("Entrance Test Fee", "Registration Fee", "Technology Fee", "Late Registration Fee"):
        t = _table_containing(soup, marker)
        if t is None or id(t) in admin_tables_seen:
            continue
        admin_tables_seen.add(id(t))
        for label, price in _flat_fee_rows(t):
            if label not in _ADMIN_FEE_LABELS:
                continue
            items.append(
                {
                    "item_name": label,
                    "price_local": price,
                    "unit": "USD/one-time"
                    if label
                    in {
                        "Entrance Test Fee",
                        "Admission Fee",
                        "Late Registration Fee",
                        "Auditing Fee",
                        "Credit-By-Examination Fee",
                        "Graduation Fee",
                        "Transcript Fee",
                        "Duplicate ID Fee",
                        "Duplicate Diploma Fee",
                        "No Sufficient Fund (NSF) Check Fee",
                    }
                    else "USD/semester",
                    "coicop_code": _EDUCATION_COICOP,
                }
            )

    if not items:
        logger.warning("[%s] no fee rows parsed from %s", _SOURCE_KEY, _URL)
        return None

    ts = get_scrape_ts()
    rows = []
    for item in items:
        row = {
            "observation_date": today.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "subnational_area": None,
            "source_key": _SOURCE_KEY,
            "coicop_code": item["coicop_code"],
            "item_name": item["item_name"],
            "price_local": item["price_local"],
            "currency": _CURRENCY,
            "unit": item["unit"],
            "source_url": _URL,
            "notes": None,
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows)
