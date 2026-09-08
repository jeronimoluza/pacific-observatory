"""PNG Power Ltd (PPL) -- electricity tariff schedule (COICOP 04.5.1).

pngpower.com.pg is a bare React/Vite SPA (no server-rendered content at
all); the tariff schedule is not behind an API -- it is a static PDF
linked from a client-side route, found by reading the app's JS bundle for
a ``href:"/docs/...tariff-schedule...pdf"`` literal (JS object notation,
not HTML markup -- a plain `href="..."` regex will not match):
``/docs/revised-2026-amended-tariff-schedule-2nd-quarter.pdf``. There is
no archive of past schedules discoverable from the site; this fetcher
snapshots whatever PDF is currently linked (single-document snapshot,
matching the guidance for tariff schedules with no visible archive).

The PDF's schedule table sits in a two-column page layout (table on the
left ~48% of the page width, a "Excluded Services" / definitions panel on
the right). ``pdftotext -layout`` and pdfplumber's default
``extract_text()`` both bleed the right-column prose into the table rows.
The fix: filter page characters to ``x0 < 405`` (empirically the
table's rightmost column, "NEW TARIFFS", ends at x1~392; the right
column's first word starts at x0~422) via ``page.filter(...)`` before
calling ``extract_text(layout=True)`` -- this reproduces the ruled table
cleanly as plain text with no cross-column bleed.

Only the "SCHEDULE OF 2025 (OLD) & 2026 (NEW) ELECTRICITY TARIFFS" table
(sections A-D: Industrial / General Supply / Domestic / Public Lighting)
is parsed. The second table further down the same column ("Schedule
Services" -- connection fees, meter testing, reconnection charges) is
intentionally NOT emitted here: those are one-off administrative charges,
not a recurring per-kWh/month electricity price, and mixing them into a
04.5.1 series would be a different row shape.

Only the NEW (2026) column is emitted -- the OLD (2025) column is carried
in ``notes`` for reference. ``toea/kWh`` values are divided by 100 to
Kina/kWh; ``Kina/*`` values are emitted as-is.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd
import pdfplumber

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Papua New Guinea"
_CURRENCY = "PGK"
_SOURCE_KEY = "pg_pngpower_tariff"
_COICOP = "04.5.1.0"
_HOME_URL = "https://pngpower.com.pg/"
_TARIFF_PDF_RE = re.compile(r'href:"(/docs/[^"]*tariff-schedule[^"]*\.pdf)"')
_APP_JS_RE = re.compile(r'<script[^>]*src="(/assets/index-[^"]+\.js)"')

_ROW_RE = re.compile(
    r"^(.+?)\s+(toea/kWh|Kina/kVA/month|Kina/month|Kina/receipt|Kina/annum)"
    r"\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s*$"
)
_NOISE = ("SCHEDULE", "TARIFF CATEGORY", "OLD TARIFFS", "Type of fitting")
_END_MARKER = "In addition to electricity"
_EFFECTIVE_RE = re.compile(
    r"from the (\d{1,2})(?:st|nd|rd|th) of ([A-Za-z]+) (\d{4})"
)
_MONTHS = {
    m: i
    for i, m in enumerate(
        [
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december",
        ],
        start=1,
    )
}
_UNIT_MAP = {
    "toea/kWh": "kWh",
    "Kina/kVA/month": "kVA/month",
    "Kina/month": "month",
    "Kina/receipt": "receipt",
    "Kina/annum": "year",
}
_IDENT = ["source_key", "observation_date", "item_name"]


def _find_pdf_url(session) -> str | None:
    try:
        home = session.get(_HOME_URL, timeout=60)
        home.raise_for_status()
    except Exception:
        logger.exception("[%s] could not load %s", _SOURCE_KEY, _HOME_URL)
        return None
    m = _APP_JS_RE.search(home.text)
    if not m:
        logger.warning("[%s] no app bundle script tag found on %s", _SOURCE_KEY, _HOME_URL)
        return None
    js_url = "https://pngpower.com.pg" + m.group(1)
    try:
        js = session.get(js_url, timeout=60)
        js.raise_for_status()
    except Exception:
        logger.exception("[%s] could not load app bundle %s", _SOURCE_KEY, js_url)
        return None
    pm = _TARIFF_PDF_RE.search(js.text)
    if not pm:
        logger.warning("[%s] no tariff-schedule PDF path found in app bundle", _SOURCE_KEY)
        return None
    return "https://pngpower.com.pg" + pm.group(1)


def _extract_table_text(content: bytes) -> str | None:
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            page = pdf.pages[0]
            left = page.filter(lambda obj: obj.get("x0", 0) < 405)
            text = left.extract_text(layout=True)
    except Exception:
        logger.exception("[%s] could not open/parse tariff PDF", _SOURCE_KEY)
        return None
    return text


def _parse_effective_date(text: str) -> date | None:
    m = _EFFECTIVE_RE.search(text)
    if not m:
        return None
    dd, month, yyyy = m.groups()
    mon = _MONTHS.get(month.lower())
    if not mon:
        return None
    try:
        return date(int(yyyy), mon, int(dd))
    except ValueError:
        return None


def _parse_rows(text: str) -> list[tuple[str, str, str, float, float]]:
    text = text.replace("Kina/kVA/mont", "Kina/kVA/month")
    section: str | None = None
    rows: list[tuple[str, str, str, float, float]] = []
    for raw_line in text.split("\n"):
        line = raw_line.rstrip()
        if _END_MARKER in line:
            break
        m = _ROW_RE.match(line)
        if m:
            label, unit, old_s, new_s = m.groups()
            try:
                old_v = float(old_s.replace(",", ""))
                new_v = float(new_s.replace(",", ""))
            except ValueError:
                continue
            rows.append((section or "", label.strip(), unit, old_v, new_v))
            continue
        s = line.strip()
        if not s or s == "h":
            continue
        if any(n in s for n in _NOISE):
            continue
        section = s
    return rows


def fetch_pg_pngpower_tariff(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    pdf_url = _find_pdf_url(session)
    if not pdf_url:
        return None

    try:
        resp = session.get(pdf_url, timeout=90)
        resp.raise_for_status()
    except Exception:
        logger.exception("[%s] failed to fetch %s", _SOURCE_KEY, pdf_url)
        return None

    text = _extract_table_text(resp.content)
    if not text:
        return None

    eff_date = _parse_effective_date(text)
    if eff_date is None:
        logger.warning(
            "[%s] could not find an effective date in the PDF text -- skipping",
            _SOURCE_KEY,
        )
        return None
    if eff_date <= cutoff:
        logger.info("[%s] effective date %s <= cutoff=%s, nothing new", _SOURCE_KEY, eff_date, cutoff)
        return None

    parsed = _parse_rows(text)
    if not parsed:
        logger.warning("[%s] no rows parsed from %s", _SOURCE_KEY, pdf_url)
        return None

    ts = get_scrape_ts()
    out: list[dict] = []
    for section, label, unit, old_v, new_v in parsed:
        price = round(new_v / 100.0, 4) if unit == "toea/kWh" else new_v
        record = {
            "observation_date": eff_date.isoformat(),
            "period_kind": "effective_from",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP,
            "item_name": f"{section} — {label}" if section else label,
            "price_local": price,
            "currency": _CURRENCY,
            "unit": _UNIT_MAP.get(unit, unit),
            "effective_from": eff_date.isoformat(),
            "source_url": pdf_url,
            "notes": f"Prior (2025) rate for the same line: {old_v}.",
            "scrape_ts": ts,
            "observation_hash": None,
        }
        record["observation_hash"] = make_hash(record, _IDENT)
        out.append(record)

    logger.info("[%s] %d rows from %s (effective %s)", _SOURCE_KEY, len(out), pdf_url, eff_date)
    df = pd.DataFrame(out).drop_duplicates(subset=["observation_hash"])
    return df
