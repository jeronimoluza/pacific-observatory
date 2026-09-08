"""Kiribati Ministry of Commerce, Industry and Cooperatives (MCIC) --
statutory Price (Regulation) Orders / "control price" schedules.

Kiribati has no scrapeable retail e-commerce at all (see the country
inventory: Punjas Kiribati is corporate-only, MOEL's Wix storefront has dead
"Shop Now" links, and every other channel is a Facebook page). This fetcher
is therefore Kiribati's only item-level food and tobacco price source.

Under the Prices Ordinance (Cap 75), MCIC gazettes a maximum wholesale AND
maximum retail price for ~120 named branded products -- flour, rice, sugar,
potatoes, powdered milk, infant formula, breakfast cereals, cordial, baby
food, tobacco, plus a non-food tail (exercise books, bar soap, benzene,
kerosene, engine oil, bicycles, batteries, mosquito nets). The Orders are
published as PDFs listed at ``mtcic.gov.ki/price-order/``; the fetcher
resolves whatever is currently linked there rather than hardcoding
filenames, so a newly gazetted Order is picked up without a code change.

IMPORTANT CAVEATS (both flagged in the YAML as well):

1. This is an ADMINISTERED CEILING price, not an observed transaction price.
   ``analytical_role: official_avg`` and ``channel: null`` follow from that.
   Rows are the legal maximum a Kiribati retailer may charge for the pack
   named in ``item_name``; realized shelf prices sit at or below them.

2. Only a minority of the archive is machine-readable. Of the 21 PDFs linked
   at /price-order/ (measured 2026-09-05): 6 carry no date in the filename
   and are skipped, and 12 of the remaining 15 yield no extractable table --
   11 are scanned images with zero text layer (including the newest,
   ``price-regulation-order-no-1-of-2024-2.pdf``), and
   ``price-control-22nd-june-2018.pdf`` has a text layer but no ruled table,
   so pdfplumber's table extractor returns nothing for it. This environment
   has no OCR installed. All three skip populations are logged explicitly,
   never silently dropped. Only 3 Orders parse, so the newest usable vintage
   is 2022-06-14; ``cutoff`` will pin there until either a new Order ships
   with a text layer or an OCR path is added.

Layout is NOT stable across vintages. 2022 Orders publish either one region
(Gilbert Group, or Line & Phoenix Group) in 5 columns, or three regions
(Gilbert Group / Christmas Island / Tabuaeran & Teraina) in 13 columns. The
parser reads the region banner above the "Wholesale" header row and derives
the number of 4-column region blocks from the row width instead of assuming
one shape. Within every block the column order is the same:

    <brand + pack> | wholesale | retail | unit-normalised | unit-normalised

Only the *retail* column is emitted as ``price_local`` (the consumer-facing
ceiling); the matching wholesale figure is carried in ``notes``. The two
trailing columns are per-kg/per-lb or per-piece restatements of the same
price and would double-count if emitted as separate observations.

Numeric cells in the source text layer carry stray intra-number spaces
("4 6.00", "0 .85") from the PDF's glyph positioning. Those are stripped
before parsing, and every parsed value is bounds-checked; a cell that still
does not read as a positive number is dropped rather than guessed at.
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

_COUNTRY = "Kiribati"
_CURRENCY = "AUD"
_SOURCE_KEY = "ki_mcic_price_control"
_INDEX_URL = "http://mtcic.gov.ki/price-order/"
_IDENT = ["source_key", "observation_date", "subnational_area", "item_name"]

_PDF_HREF_RE = re.compile(
    r'href="(http://mtcic\.gov\.ki/download/\d+/price-control/\d+/[^"]+\.pdf)"',
    re.I,
)

# "...as-at-14-06-2022.pdf" / "...-13-as-at-17-08-2022.pdf"
_DMY_RE = re.compile(r"(\d{2})-(\d{2})-(\d{4})")
# "price-control-22nd-june-2018.pdf" / "control-price-6th-april-2018.pdf"
_ORDINAL_RE = re.compile(
    r"(\d{1,2})(?:st|nd|rd|th)-([a-z]+)-(\d{4})",
    re.I,
)
_MONTHS = {
    m: i
    for i, m in enumerate(
        [
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ],
        start=1,
    )
}

# "1. Flour", "10. Tobacco", "9. Baby Food (bottle) Per carton"
_SECTION_RE = re.compile(r"^\d{1,2}\s*\.\s*([A-Za-z].*)$")
# Trailing column-unit hints the PDF glues onto the section heading.
_SECTION_NOISE_RE = re.compile(
    r"\s*(per\s+(carton|piece|pieces|bottle|packet|bar|tin|drum|litre|yard|"
    r"inner/pcs)|wp/pcs|r/p/pcs|pcs)\b.*$",
    re.I,
)

_MAX_PRICE = 100_000.0


def _parse_doc_date(url: str) -> date | None:
    name = url.rsplit("/", 1)[-1].lower()
    m = _DMY_RE.search(name)
    if m:
        dd, mm, yyyy = (int(g) for g in m.groups())
        try:
            return date(yyyy, mm, dd)
        except ValueError:
            return None
    m = _ORDINAL_RE.search(name)
    if m:
        dd, month, yyyy = m.group(1), m.group(2), m.group(3)
        mon = _MONTHS.get(month)
        if mon:
            try:
                return date(int(yyyy), mon, int(dd))
            except ValueError:
                return None
    return None


def _num(cell: str | None) -> float | None:
    """Parse a price cell, tolerating the PDF's stray intra-number spaces."""
    if not cell:
        return None
    text = re.sub(r"\s+", "", str(cell)).replace("$", "").replace(",", "")
    # Some wholesale cells publish "per-carton/per-unit" as "15.25/2.50".
    # Only the leading figure belongs to the column.
    text = text.split("/", 1)[0]
    if not text:
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    if value <= 0 or value > _MAX_PRICE:
        return None
    return value


def _clean_section(text: str) -> str | None:
    m = _SECTION_RE.match(text.strip())
    if not m:
        return None
    label = _SECTION_NOISE_RE.sub("", m.group(1)).strip(" .:-")
    # "5.Prices Regulation Order (No.1) 2022 is repealed" is a preamble line,
    # not a commodity section.
    if not label or "regulation order" in label.lower():
        return None
    return label


def _region_labels(rows: list[list[str | None]]) -> list[str]:
    """Region names for each 4-column block, read off the banner row that sits
    directly above the 'Wholesale' header row."""
    header_idx = next(
        (
            i
            for i, r in enumerate(rows)
            if r and any(c and "wholesale" in str(c).lower() for c in r)
        ),
        None,
    )
    if header_idx is None:
        return []
    width = len(rows[header_idx])
    n_blocks = max(1, (width - 1) // 4)
    banner = rows[header_idx - 1] if header_idx > 0 else []
    labels: list[str] = []
    for block in range(n_blocks):
        col = 1 + 4 * block
        raw = banner[col] if col < len(banner) else None
        label = re.sub(r"\s+", " ", str(raw)).strip() if raw else ""
        labels.append(label or f"Region {block + 1}")
    return labels


def _parse_pdf(content: bytes) -> tuple[list[str], list[list[str | None]]]:
    rows: list[list[str | None]] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                rows.extend(table)
    return _region_labels(rows), rows


def _rows_from_doc(
    *, rows: list[list[str | None]], regions: list[str], doc_date: date, url: str
) -> list[dict]:
    ts = get_scrape_ts()
    out: list[dict] = []
    section: str | None = None
    for row in rows:
        if not row:
            continue
        first = str(row[0] or "").strip()
        if not first:
            continue
        heading = _clean_section(first)
        if heading:
            section = heading
            continue
        if section is None:
            # Still in the preamble (repeal notice, order number, banner).
            continue
        for block, region in enumerate(regions):
            w_col, r_col = 1 + 4 * block, 2 + 4 * block
            if r_col >= len(row):
                continue
            retail = _num(row[r_col])
            if retail is None:
                continue
            wholesale = _num(row[w_col])
            item = re.sub(r"\s+", " ", first)
            note = (
                "Statutory maximum retail price under the Prices Ordinance "
                "(Cap 75); administered ceiling, not an observed shelf price."
            )
            if wholesale is not None:
                note += f" Maximum wholesale price for the same pack: {wholesale:.2f}."
            record = {
                "observation_date": doc_date.isoformat(),
                "period_kind": "effective_from",
                "country": _COUNTRY,
                "subnational_area": region,
                "source_key": _SOURCE_KEY,
                "coicop_code": None,
                "item_name": f"{section} - {item}",
                "price_local": retail,
                "currency": _CURRENCY,
                "unit": None,
                "source_url": url,
                "notes": note,
                "scrape_ts": ts,
                "observation_hash": None,
            }
            record["observation_hash"] = make_hash(record, _IDENT)
            out.append(record)
    return out


def fetch_ki_mcic_price_control(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    try:
        index = session.get(_INDEX_URL, timeout=60)
        index.raise_for_status()
    except Exception:
        logger.exception("[%s] could not load %s", _SOURCE_KEY, _INDEX_URL)
        return None

    urls = sorted(set(_PDF_HREF_RE.findall(index.text)))
    if not urls:
        logger.warning(
            "[%s] no price-control PDF links found on %s -- page layout may "
            "have changed",
            _SOURCE_KEY,
            _INDEX_URL,
        )
        return None
    logger.info("[%s] %d Order PDFs linked", _SOURCE_KEY, len(urls))

    dated = [(u, _parse_doc_date(u)) for u in urls]
    undated = [u for u, d in dated if d is None]
    if undated:
        logger.info(
            "[%s] %d PDF(s) skipped -- no date parseable from filename: %s",
            _SOURCE_KEY,
            len(undated),
            ", ".join(u.rsplit("/", 1)[-1] for u in undated),
        )

    todo = [(u, d) for u, d in dated if d is not None and d > cutoff]
    if not todo:
        logger.info("[%s] no Order newer than cutoff=%s", _SOURCE_KEY, cutoff)
        return None

    all_rows: list[dict] = []
    no_text: list[str] = []
    for url, doc_date in sorted(todo, key=lambda t: t[1]):
        try:
            resp = session.get(url, timeout=120)
            resp.raise_for_status()
            regions, rows = _parse_pdf(resp.content)
        except Exception:
            logger.exception("[%s] failed to read %s", _SOURCE_KEY, url)
            continue
        if not regions or not rows:
            no_text.append(url.rsplit("/", 1)[-1])
            continue
        doc_rows = _rows_from_doc(
            rows=rows, regions=regions, doc_date=doc_date, url=url
        )
        logger.info(
            "[%s] %s (%s): %d rows across regions %s",
            _SOURCE_KEY,
            url.rsplit("/", 1)[-1],
            doc_date,
            len(doc_rows),
            regions,
        )
        all_rows.extend(doc_rows)

    if no_text:
        logger.warning(
            "[%s] %d of %d Order PDF(s) are scanned images with no text layer "
            "and were skipped (no OCR available): %s",
            _SOURCE_KEY,
            len(no_text),
            len(todo),
            ", ".join(no_text),
        )

    if not all_rows:
        logger.warning(
            "[%s] no rows parsed from %d Order PDF(s)", _SOURCE_KEY, len(todo)
        )
        return None

    df = pd.DataFrame(all_rows).drop_duplicates(subset=["observation_hash"])
    return df
