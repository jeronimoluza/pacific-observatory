"""American Samoa Community College tuition and fee schedule."""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://www.amsamoa.edu/tuitionandfees.html"
_COUNTRY = "American Samoa"
_CURRENCY = "USD"
_SOURCE_KEY = "as_ascc_tuition"
_COICOP = "10.4.0.0"
_IDENT = ["source_key", "observation_date", "item_name", "unit"]

# "$150.00 Resident"  -> price first, qualifier after
_LEAD_PRICE_RE = re.compile(r"^\$(?P<price>\d[\d,]*\.\d{2})\s*(?P<qual>.*)$")
# "Late Registration Fee: $20.00 (non-refundable)" -> label first
_LABEL_PRICE_RE = re.compile(
    r"^(?P<label>[A-Za-z][^$]{2,70}?)\s*:?\s*"
    r"\$(?P<price>\d[\d,]*\.\d{2})\s*(?P<qual>.*)$"
)

_UNIT_RE = re.compile(
    r"per\s+(credit|check|course|student|degree|official copy|student copy|semester)",
    re.I,
)

_SECTIONS = {
    "Tuition Cost Per Credit",
    "Spring and Fall Term Fees",
    "Summer Term Fees",
    "Additional Fees",
    "Transcript Fees",
    "Dishonored Check Fees",
    "Graduation & Diploma Fees",
    "Student Records Fees",
    "Technology Fee",
}

# Prose paragraphs restate figures already captured from the fee tables.
# Words that are never a fee name on their own -- they continue the line above.
_CONTINUATION_WORDS = {"additional", "total"}

_SKIP_LINES = {
    # Link text that sits directly above the per-credit tuition figures and
    # would otherwise be picked up as their label.
    "ASCC 2021 Change of Tuition and Fees Approval",
}

_SKIP_PREFIXES = (
    "all ascc students are required",
    "this fee provides",
    "if for any reason",
    "an additional",
    "refer to our",
    "for more information",
    "tuition refunds will be issued",
    "the american samoa community college reserves",
)


def _clean(value: str) -> str:
    value = value.replace("\xa0", " ")
    value = re.sub(r"[.…]{2,}", " ", value)
    return " ".join(value.split())


def _normalise_label(label: str) -> str:
    """Trim the connective words a prose sentence leaves on a label."""
    label = re.sub(r"^The fee for\s+", "", label, flags=re.I)
    label = re.sub(r"\s+(is|are|of)$", "", label, flags=re.I)
    return _clean(label)


def _unit(text: str) -> str:
    match = _UNIT_RE.search(text)
    if match is None:
        return "item"
    return match.group(1).lower().replace(" ", "_")


def _row(item_name: str, price: float, unit: str, section: str, ts: str) -> dict:
    row = {
        "observation_date": date.today().isoformat(),
        "period_kind": "current_tariff",
        "country": _COUNTRY,
        "subnational_area": None,
        "source_key": _SOURCE_KEY,
        "coicop_code": _COICOP,
        "item_name": item_name[:500],
        "price_local": round(price, 2),
        "currency": _CURRENCY,
        "unit": unit,
        "source_url": _URL,
        "notes": f"ASCC published tuition/fee schedule; section={section}",
        "scrape_ts": ts,
        "observation_hash": None,
    }
    row["observation_hash"] = make_hash(row, _IDENT)
    return row


def _parse(text: str, ts: str) -> list[dict]:
    rows: list[dict] = []
    section = "Tuition and Fees"
    previous_label = ""

    for raw_line in text.splitlines():
        line = _clean(raw_line)
        if not line:
            continue
        if line in _SKIP_LINES:
            continue
        if line in _SECTIONS:
            section = line
            # A price-leading line directly under a heading takes the heading
            # as its label ("Tuition Cost Per Credit" + "Resident").
            previous_label = line
            continue
        if line.lower().startswith(_SKIP_PREFIXES):
            continue

        lead = _LEAD_PRICE_RE.match(line)
        if lead is not None:
            qualifier = _clean(lead.group("qual").split(".")[0])
            label = _clean(f"{previous_label} {qualifier}")
            if not label:
                continue
            price = float(lead.group("price").replace(",", ""))
            rows.append(_row(label, price, _unit(line), section, ts))
            continue

        labelled = _LABEL_PRICE_RE.match(line)
        if labelled is not None:
            label = _normalise_label(labelled.group("label"))
            # "Complete Withdrawal from ASCC:" / "Additional $10.00 per student"
            # -- a bare continuation word needs the line above it to mean
            # anything.
            if label.lower() in _CONTINUATION_WORDS and previous_label:
                label = f"{previous_label} {label}"
            qualifier = _clean(labelled.group("qual").split(".")[0])
            price = float(labelled.group("price").replace(",", ""))
            name = f"{label} {qualifier}".strip() if qualifier else label
            rows.append(_row(_clean(name), price, _unit(line), section, ts))
            previous_label = ""
            continue

        if "$" not in line and len(line) <= 70:
            candidate = line.rstrip(":")
            # The page splits "Complete Withdrawal from ASCC:" / "Additional" /
            # "$10.00 per student" across three nodes; a bare continuation word
            # extends the label above it rather than replacing it.
            if candidate.lower() in _CONTINUATION_WORDS and previous_label:
                previous_label = f"{previous_label} {candidate}"
            else:
                previous_label = candidate

    return rows


def fetch_as_ascc_tuition(cutoff: date) -> pd.DataFrame | None:
    today = date.today()
    if today <= cutoff:
        return None

    session = get_session()
    session.headers.update({"User-Agent": "Mozilla/5.0 price-research"})
    resp = session.get(_URL, timeout=60)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    text = soup.get_text("\n", strip=True)
    ts = get_scrape_ts()
    rows = _parse(text, ts)

    if not rows:
        logger.warning("[%s] no tuition/fee rows parsed", _SOURCE_KEY)
        return None
    out = pd.DataFrame(rows).drop_duplicates(subset=["observation_hash"])
    logger.info("[%s] parsed %d tuition/fee rows", _SOURCE_KEY, len(out))
    return out
