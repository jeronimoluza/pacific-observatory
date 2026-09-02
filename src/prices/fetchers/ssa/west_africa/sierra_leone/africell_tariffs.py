"""Africell Sierra Leone -- prepaid data bundle and combo bundle tariffs.

Africell SL (africell.sl) publishes its full mobile data-bundle price list as
plain server-rendered HTML tables (Prepaid Bundles, Postpaid Bundles, Mifi and
Router Unlimited Bundles, Social Media Bundles) plus a separate combo-bundle
table (data + voice minutes + SMS). No JS rendering required; no WAF.

Emits PriceObservation rows (analytical_role: tariff, coicop_classification:
source_curated -> "08.3.0" telecommunication services).

CURRENCY: prices are labelled "NLe" (New Leone) on the data-bundles page and
"Le" on the combo-bundles page -- both are the SAME post-2022-redenomination
currency (SLE); "Le" here is just an informal shorthand for the new leone, NOT
the pre-2022 SLL. Confirmed by magnitude cross-check: a 15GB/30-day bundle is
"NLe 300" and a 650MB/monthly combo bundle is "Le 30" -- both in the same
single/low-hundreds-of-units range that matches Orange SL's data-bundle
pricing on the same date (see orange_tariffs.py notes), which is consistent
with genuine SLE pricing (~1-30 USD/month range for mobile data in Sierra
Leone) and NOT plausible as raw pre-2022 SLL (which would price a 15GB bundle
at a fraction of one hundredth of one US cent). All emitted rows use
currency="SLE".
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
import requests

from prices.fetchers.utils import get_scrape_ts, make_hash

logger = logging.getLogger(__name__)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_PAGES = {
    "https://www.africell.sl/services/data-bundles/": "data_bundle",
    "https://www.africell.sl/services/combo-bundles/": "combo_bundle",
}
_COUNTRY = "Sierra Leone"
_SOURCE_KEY = "sl_africell_tariffs"
_CURRENCY = "SLE"
_COICOP_MAP_DEFAULT = "08.3.0"
_IDENT = ["source_key", "item_name", "unit"]

_TAG_RE = re.compile(r"<[^>]+>")
_PRICE_RE = re.compile(r"(?:NLe|Le)\s*([\d,]+\.?\d*)", re.IGNORECASE)
_NUMERIC_RE = re.compile(r"^[\d,]+$")

# Walk the document in order, picking up whichever of these fires next:
# a top-level section heading, a colspan sub-heading, or a full table row.
_WALK_RE = re.compile(
    r'<div class="decolor font18 mb-3 bold upper">([^<]+)</div>'
    r'|<tr[^>]*>\s*<th colspan="4">([^<]+)</th>\s*</tr>'
    r"|<tr[^>]*>(.*?)</tr>",
    re.IGNORECASE | re.DOTALL,
)
_CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.IGNORECASE | re.DOTALL)


def _clean(cell: str) -> str:
    return _TAG_RE.sub("", cell).strip()


def _parse_page(html: str, section_label: str) -> list[dict]:
    rows: list[dict] = []
    page_section = section_label
    sub_section = ""
    for m in _WALK_RE.finditer(html):
        section_hdr, subsection_hdr, row_html = m.groups()
        if section_hdr is not None:
            page_section = section_hdr.strip()
            sub_section = ""
            continue
        if subsection_hdr is not None:
            sub_section = subsection_hdr.strip()
            continue

        cells = [_clean(c) for c in _CELL_RE.findall(row_html)]
        if len(cells) < 3:
            continue
        price_cell = None
        for c in cells:
            if _PRICE_RE.search(c):
                price_cell = c
                break
        if price_cell is None:
            continue
        m2 = _PRICE_RE.search(price_cell)
        try:
            price = float(m2.group(1).replace(",", ""))
        except ValueError:
            continue
        other = [c for c in cells if c and c is not price_cell]
        # validity/period is conventionally the last non-empty cell
        validity = other[-1] if other else ""
        descriptor_cells = other[:-1] if len(other) > 1 else other
        # drop a bare numeric echo column (e.g. "MBs" repeating "15MB" as "15")
        descriptor_cells = [
            c for c in descriptor_cells if not _NUMERIC_RE.match(c)
        ] or descriptor_cells
        descriptor = " ".join(c for c in descriptor_cells if c)
        if not descriptor:
            continue
        label_parts = [p for p in (page_section, sub_section, descriptor) if p]
        item_name = f"Africell {' '.join(label_parts)} ({validity})".strip()
        rows.append(
            {
                "item_name": item_name,
                "price_local": price,
                "unit": validity or "unspecified",
                "category": page_section,
            }
        )
    return rows


def fetch_sl_africell_tariffs(cutoff: date) -> pd.DataFrame | None:
    session = requests.Session()
    session.headers.update({"User-Agent": _UA})

    today = date.today()
    if today <= cutoff:
        return None

    parsed: list[dict] = []
    for url, section_label in _PAGES.items():
        try:
            resp = session.get(url, timeout=30)
        except requests.RequestException as exc:
            logger.warning("[%s] Request failed for %s: %s", _SOURCE_KEY, url, exc)
            continue
        if resp.status_code != 200:
            logger.warning("[%s] HTTP %s for %s", _SOURCE_KEY, resp.status_code, url)
            continue
        page_rows = _parse_page(resp.text, section_label)
        for r in page_rows:
            r["source_url"] = url
        parsed.extend(page_rows)

    if not parsed:
        logger.warning("[%s] No tariff rows parsed", _SOURCE_KEY)
        return None

    rows: list[dict] = []
    for p in parsed:
        row = {
            "observation_date": today.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": p["item_name"],
            "price_local": p["price_local"],
            "currency": _CURRENCY,
            "unit": p["unit"],
            "coicop_code": _COICOP_MAP_DEFAULT,
            "source_url": p["source_url"],
            "notes": p["category"],
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows) if rows else None
