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

IMPORTANT CAVEATS (all flagged in the YAML as well):

1. This is an ADMINISTERED CEILING price, not an observed transaction price.
   ``analytical_role: official_avg`` and ``channel: null`` follow from that.
   Rows are the legal maximum a Kiribati retailer may charge for the pack
   named in ``item_name``; realized shelf prices sit at or below them.

2. Most of the archive is a scan, and is read by OCR. Of the 21 PDFs linked
   at /price-order/ (measured 2026-09-11) only 3 carry a text layer with a
   ruled table pdfplumber can see. The rest are image-only, so when
   ``_parse_pdf`` comes back empty the page is re-read through
   ``prices.fetchers.ocr`` -- see that module for why the scan is parsed off
   its own ruled lines rather than off OCR line text, and how strictly the
   values are filtered. OCR rows are additionally checked here against the
   Order's own internal arithmetic before they are emitted:

     * the retail figure must read as ``<digits>.<2 digits>`` and land in a
       plausible AUD ceiling range;
     * the matching wholesale figure, when it was read, must not exceed it;
     * the per-kg and per-lb restatements of the same price, when both were
       read, must sit near the 2.2046 kg/lb ratio -- a block whose columns
       have shifted will not, and that is the check that catches a shift the
       naked value cannot.

   Measured on a full 2015-01-01 rebuild (2026-09-11): 935 rows, of which
   689 come from the 3 text-layer Orders and 246 from 2 OCR'd scans, at an
   OCR reject rate of 17.0% (68 of 401 candidate cells). The newest usable
   vintage moves from 2022-06-14 to 2024-02-22 -- the Prices (Regulation)
   Order No.1 of 2024, which is a scan.

   16 of the 21 PDFs still yield nothing. They are not a single population:
   some are amendment notices with no ruled table at all, and some (notably
   ``price-control-23th-august-2021.pdf``) are scans whose rules are too
   faint to detect at any threshold. All are logged by name every run.

3. OCR rows carry NO ``<section> - `` prefix on ``item_name``, unlike
   text-layer rows. The commodity headings ("2) Rice") are drawn in the same
   column as the products and a scan drops them often enough -- "2) Rice"
   came back as "ce" on the 2024 Order -- that carrying the last heading
   forward files every rice line under Flour. The product names already
   carry the commodity ("Jasmine 5kg Rice"), so the prefix is dropped rather
   than guessed. The consequence is that an OCR'd vintage does NOT join to a
   text-layer vintage on ``item_name`` alone.

4. ``subnational_area`` is part of the observation identity, so an OCR'd
   region banner is resolved back to one of Kiribati's four gazetted island
   groups (``_canonical_region``) and a block whose banner does not resolve
   is dropped. On the 2020 Order that costs 2 of 3 blocks: the banner came
   back as "Region 2"/"Region 3" (empty cells), which is not a series key.

5. Six PDFs carry only a year in the filename ("...-no-1-of-2024-2.pdf",
   "signed-price-order-pao-16-2022.pdf"). Their date comes from the
   listing's own "Date added: DD-MM-YYYY" field instead, which is the
   publisher's upload date rather than the Order's gazetted commencement
   date -- the 2024 Order's own commencement line is left blank in the PDF.
   Before this fallback those six, including the 2024 Order, were skipped
   outright.

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

import difflib
import io
import logging
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date

import pandas as pd
import pdfplumber

from prices.fetchers import ocr
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
# The WP-File-Download listing prints the publisher's own upload date next to
# every file ("Date added: 22-02-2024"). That is the authoritative date for the
# Orders whose filename carries only a year ("...-no-1-of-2024-2.pdf") -- see
# _doc_date().
_DATE_ADDED_RE = re.compile(
    r"Date added:</span>\s*(\d{2})-(\d{2})-(\d{4})", re.I
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

# "1. Flour", "10. Tobacco", "9. Baby Food (bottle) Per carton", and the
# 2024 Order's "1)Flour" / "15) Bicycle".
_SECTION_RE = re.compile(r"^(\d{1,2})\s*[.)]\s*([A-Za-z].*)$")
# Trailing column-unit hints the PDF glues onto the section heading.
_SECTION_NOISE_RE = re.compile(
    r"\s*(per\s+(carton|piece|pieces|bottle|packet|bar|tin|drum|litre|yard|"
    r"inner/pcs)|wp/pcs|r/p/pcs|pcs)\b.*$",
    re.I,
)

# Scanned pages carry a running "PAGE 3" / "Page 3" in the commodity column.
_PAGE_MARK_RE = re.compile(r"\b(?:PAGE|Page)\s*\d+\b")

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


def _clean_section(text: str) -> tuple[int, str] | None:
    """Parse a numbered commodity heading ("3. Sugar", "15) Bicycle").

    Returns the heading's own ordinal alongside the label; the ordinal is what
    lets the OCR path notice that a heading went unread -- see _rows_from_doc.
    """
    m = _SECTION_RE.match(text.strip())
    if not m:
        return None
    label = _SECTION_NOISE_RE.sub("", m.group(2)).strip(" .:-")
    # "5.Prices Regulation Order (No.1) 2022 is repealed" is a preamble line,
    # not a commodity section.
    if not label or "regulation order" in label.lower():
        return None
    return int(m.group(1)), label


def _region_labels(rows: list[list[str | None]]) -> list[str]:
    """Region names for each 4-column block, read off the banner row that sits
    directly above the 'Wholesale' header row.

    The banner cell is joined across the whole 4-column span rather than read
    out of the block's first column: a text-layer table puts the name in one
    merged cell (the other three are empty, so joining is a no-op), but an
    OCR'd scan has no merged cells and spreads "LINE & PHOENIX GROUP" over
    three of them.
    """
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
        span = banner[1 + 4 * block : 5 + 4 * block]
        raw = " ".join(str(c) for c in span if c)
        label = re.sub(r"\s+", " ", raw).strip(" |.-")
        labels.append(label or f"Region {block + 1}")
    return labels


def _parse_pdf(content: bytes) -> tuple[list[str], list[list[str | None]]]:
    rows: list[list[str | None]] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                rows.extend(table)
    return _region_labels(rows), rows


def _ocr_pdf(content: bytes) -> tuple[list[str], list[list[str | None]]]:
    """Same shape as _parse_pdf, but for a scan with no text layer.

    Only pages whose recovered grid has the document's modal column count are
    kept, and that count must itself be a legal Order shape (one commodity
    column plus whole 4-column region blocks). A scan page whose ruled lines
    came back short is therefore dropped entirely rather than contributing a
    row whose columns mean something other than the header says they do.
    """
    grids = ocr.page_grids(content)
    if not grids:
        return [], []
    widths = Counter(len(r) for g in grids for r in g)
    if not widths:
        return [], []
    modal, _ = widths.most_common(1)[0]
    if modal < 5 or (modal - 1) % 4 != 0:
        logger.info(
            "[%s] OCR grid width %d is not a 1+4n Order shape -- page(s) dropped",
            _SOURCE_KEY,
            modal,
        )
        return [], []
    rows = [r for g in grids for r in g if len(r) == modal]
    dropped = sum(n for w, n in widths.items() if w != modal)
    if dropped:
        logger.info(
            "[%s] OCR: %d row(s) dropped on a non-modal grid width (kept %d at "
            "width %d)",
            _SOURCE_KEY,
            dropped,
            len(rows),
            modal,
        )
    return _region_labels(rows), rows


# The island groups the Orders price separately. `subnational_area` is part of
# the observation identity, so an OCR'd banner has to be resolved back to one of
# these -- "Ibert Group" (a clipped "Gilbert Group") and the "Region 2"
# placeholder are not usable series keys, and a block whose banner does not
# resolve is dropped rather than published under a made-up area.
_CANON_REGIONS = (
    "Gilbert Group",
    "Christmas Island",
    "Tabuaeran & Teraina",
    "Line & Phoenix Group",
)
_REGION_ALIASES = {
    "linnix and line group": "Line & Phoenix Group",
    "line and phoenix group": "Line & Phoenix Group",
    "line & phoenix groups": "Line & Phoenix Group",
    "tabuaeran and teraina": "Tabuaeran & Teraina",
}


def _canonical_region(label: str) -> str | None:
    key = re.sub(r"[^a-z& ]+", " ", str(label).lower())
    key = re.sub(r"\s+", " ", key).strip()
    if not key:
        return None
    if key in _REGION_ALIASES:
        return _REGION_ALIASES[key]
    for canon in _CANON_REGIONS:
        if key == canon.lower():
            return canon
    hit = difflib.get_close_matches(
        key, [c.lower() for c in _CANON_REGIONS], n=1, cutoff=0.78
    )
    if hit:
        return next(c for c in _CANON_REGIONS if c.lower() == hit[0])
    return None


# Plausible AUD ceiling prices in a Kiribati Price Order: the cheapest
# controlled line is a single battery / bar of soap, the dearest an adult
# bicycle or a drum of engine oil.
_OCR_PRICE_LO = 0.05
_OCR_PRICE_HI = 2000.0
# 1 kg = 2.2046 lb, so a correctly aligned pair of per-kg / per-lb columns must
# sit near that ratio. A block whose columns have shifted will not.
_KG_PER_LB_LO = 1.8
_KG_PER_LB_HI = 2.7


@dataclass
class _Rejects:
    price: int = 0
    item: int = 0
    wholesale_gt_retail: int = 0
    unit_ratio: int = 0
    candidates: int = 0

    @property
    def total(self) -> int:
        return self.price + self.item + self.wholesale_gt_retail + self.unit_ratio


def _rows_from_doc(
    *,
    rows: list[list[str | None]],
    regions: list[str],
    doc_date: date,
    url: str,
    from_ocr: bool = False,
) -> tuple[list[dict], _Rejects]:
    ts = get_scrape_ts()
    out: list[dict] = []
    rej = _Rejects()
    section: str | None = None
    resolved = [_canonical_region(r) for r in regions]
    unresolved = [r for r, c in zip(regions, resolved) if c is None]
    if unresolved:
        logger.warning(
            "[%s] %s: %d region block(s) dropped -- banner %s does not resolve "
            "to a Kiribati island group",
            _SOURCE_KEY,
            url.rsplit("/", 1)[-1],
            len(unresolved),
            unresolved,
        )
    for row in rows:
        if not row:
            continue
        first = str(row[0] or "").strip()
        if from_ocr:
            # Every scanned page prints a running "PAGE n" in the commodity
            # column; it is not part of the heading or the item.
            first = _PAGE_MARK_RE.sub("", first).strip()
        if not first:
            continue
        heading = _clean_section(first)
        if heading and not from_ocr:
            section = heading[1]
            continue
        if heading and from_ocr and not any(_num(c) for c in row[1:]):
            # A heading row on a scan carries no prices; nothing else to do
            # with it, because OCR rows are not given a section prefix (below).
            continue
        if section is None and not from_ocr:
            # Still in the preamble (repeal notice, order number, banner).
            continue
        item = re.sub(r"\s+", " ", first)
        if from_ocr:
            item = _SECTION_RE.sub(r"\2", item).strip()
            if not ocr.looks_like_item_name(item):
                rej.item += 1
                continue
        # An OCR'd row is NOT given the "<section> - " prefix a text-layer row
        # gets. The commodity headings on these scans are numbered section
        # markers ("2) Rice") drawn in the same column as the products, and a
        # scan drops them often enough -- "2) Rice" came back as "ce" on the
        # 2024 Order -- that carrying the last heading forward files every rice
        # line under Flour. The product names on their own already carry the
        # commodity ("Jasmine 5kg Rice"), so the prefix is dropped rather than
        # guessed.
        for block, region in enumerate(resolved):
            if region is None:
                continue
            w_col, r_col = 1 + 4 * block, 2 + 4 * block
            kg_col, lb_col = 3 + 4 * block, 4 + 4 * block
            if r_col >= len(row):
                continue
            if from_ocr:
                rej.candidates += 1
                bounds = {"lo": _OCR_PRICE_LO, "hi": _OCR_PRICE_HI}
                retail = ocr.money(row[r_col], **bounds)
                if retail is None:
                    if row[r_col]:
                        rej.price += 1
                    continue
                wholesale = ocr.money(row[w_col], **bounds)
                if wholesale is not None and wholesale > retail:
                    # Either a shifted column or one of the gazette's own
                    # typos. Unrecoverable either way -- drop, do not publish.
                    rej.wholesale_gt_retail += 1
                    continue
                per_kg = ocr.money(
                    row[kg_col] if kg_col < len(row) else None, **bounds
                )
                per_lb = ocr.money(
                    row[lb_col] if lb_col < len(row) else None, **bounds
                )
                if per_kg and per_lb:
                    ratio = per_kg / per_lb
                    if not _KG_PER_LB_LO <= ratio <= _KG_PER_LB_HI:
                        rej.unit_ratio += 1
                        continue
            else:
                retail = _num(row[r_col])
                if retail is None:
                    continue
                wholesale = _num(row[w_col])
            name = f"{section} - {item}" if section and not from_ocr else item
            note = (
                "Statutory maximum retail price under the Prices Ordinance "
                "(Cap 75); administered ceiling, not an observed shelf price."
            )
            if wholesale is not None:
                note += f" Maximum wholesale price for the same pack: {wholesale:.2f}."
            if from_ocr:
                note += (
                    " Recovered by OCR from an image-only scan: the value is "
                    "tesseract's reading of the gazetted figure, validated "
                    "against the Order's own per-kg/per-lb columns."
                )
            record = {
                "observation_date": doc_date.isoformat(),
                "period_kind": "effective_from",
                "country": _COUNTRY,
                "subnational_area": region,
                "source_key": _SOURCE_KEY,
                "coicop_code": None,
                "item_name": name,
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
    return out, rej


def _index_dates(html: str) -> dict[str, date]:
    """Map every linked PDF url to the listing's own "Date added"."""
    out: dict[str, date] = {}
    for chunk in html.split('<div class="file"'):
        urls = _PDF_HREF_RE.findall(chunk)
        m = _DATE_ADDED_RE.search(chunk)
        if not urls or not m:
            continue
        dd, mm, yyyy = (int(g) for g in m.groups())
        try:
            added = date(yyyy, mm, dd)
        except ValueError:
            continue
        for u in urls:
            out.setdefault(u, added)
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

    added = _index_dates(index.text)
    dated: list[tuple[str, date | None, bool]] = []
    for u in urls:
        d = _parse_doc_date(u)
        dated.append((u, d or added.get(u), d is None))
    from_listing = [u for u, d, fb in dated if d is not None and fb]
    if from_listing:
        logger.info(
            "[%s] %d PDF(s) carry no date in the filename; using the listing's "
            "own \"Date added\" instead: %s",
            _SOURCE_KEY,
            len(from_listing),
            ", ".join(u.rsplit("/", 1)[-1] for u in from_listing),
        )
    undated = [u for u, d, _ in dated if d is None]
    if undated:
        logger.warning(
            "[%s] %d PDF(s) skipped -- no date from filename or listing: %s",
            _SOURCE_KEY,
            len(undated),
            ", ".join(u.rsplit("/", 1)[-1] for u in undated),
        )

    todo = [(u, d) for u, d, _ in dated if d is not None and d > cutoff]
    if not todo:
        logger.info("[%s] no Order newer than cutoff=%s", _SOURCE_KEY, cutoff)
        return None

    all_rows: list[dict] = []
    unparsed: list[str] = []
    ocr_used: list[str] = []
    totals = _Rejects()
    for url, doc_date in sorted(todo, key=lambda t: t[1]):
        name = url.rsplit("/", 1)[-1]
        try:
            resp = session.get(url, timeout=120)
            resp.raise_for_status()
            regions, rows = _parse_pdf(resp.content)
        except Exception:
            logger.exception("[%s] failed to read %s", _SOURCE_KEY, url)
            continue
        from_ocr = False
        if not regions or not rows:
            # No text layer at all, or a text layer with no ruled table that
            # pdfplumber can see. Both are recoverable from the rendered page.
            if not ocr.ocr_available():
                unparsed.append(name)
                continue
            from_ocr = True
            try:
                regions, rows = _ocr_pdf(resp.content)
            except Exception:
                logger.exception("[%s] OCR failed on %s", _SOURCE_KEY, url)
                unparsed.append(name)
                continue
            if not regions or not rows:
                unparsed.append(name)
                continue
            ocr_used.append(name)
        doc_rows, rej = _rows_from_doc(
            rows=rows,
            regions=regions,
            doc_date=doc_date,
            url=url,
            from_ocr=from_ocr,
        )
        if from_ocr:
            totals.price += rej.price
            totals.item += rej.item
            totals.wholesale_gt_retail += rej.wholesale_gt_retail
            totals.unit_ratio += rej.unit_ratio
            totals.candidates += rej.candidates
            logger.info(
                "[%s] %s (%s) OCR: %d rows kept, %d rejected of %d candidate "
                "cells (unreadable=%d, wholesale>retail=%d, per-kg/lb ratio=%d, "
                "junk item name=%d); regions %s",
                _SOURCE_KEY,
                name,
                doc_date,
                len(doc_rows),
                rej.total,
                rej.candidates,
                rej.price,
                rej.wholesale_gt_retail,
                rej.unit_ratio,
                rej.item,
                regions,
            )
        else:
            logger.info(
                "[%s] %s (%s): %d rows across regions %s",
                _SOURCE_KEY,
                name,
                doc_date,
                len(doc_rows),
                regions,
            )
        if not doc_rows:
            unparsed.append(name)
        all_rows.extend(doc_rows)

    if ocr_used and totals.candidates:
        logger.info(
            "[%s] OCR reject rate %.1f%% (%d of %d candidate cells) across %d "
            "scanned Order(s)",
            _SOURCE_KEY,
            100.0 * totals.total / totals.candidates,
            totals.total,
            totals.candidates,
            len(ocr_used),
        )
    if unparsed:
        logger.warning(
            "[%s] %d of %d Order PDF(s) yielded no usable rows even after OCR: "
            "%s",
            _SOURCE_KEY,
            len(unparsed),
            len(todo),
            ", ".join(unparsed),
        )

    if not all_rows:
        logger.warning(
            "[%s] no rows parsed from %d Order PDF(s)", _SOURCE_KEY, len(todo)
        )
        return None

    df = pd.DataFrame(all_rows).drop_duplicates(subset=["observation_hash"])
    return df
