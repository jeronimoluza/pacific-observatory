"""Papua New Guinea Independent Consumer & Competition Commission (ICCC) --
monthly Indicative Retail Fuel Price (IRP) notices.

ICCC publishes a press-release post roughly once a month at
https://iccc.gov.pg/category/monthly-fuel-price/ announcing the maximum
indicative retail price for Petrol, Diesel and Kerosene at ~25 named centres
across PNG. Each post links one or more PDFs; only some vintages carry a
text layer. The fetcher tries every PDF linked from a post and keeps whichever
one parses into rows -- it does not trust the filename to identify "the"
price-table PDF, because naming is inconsistent across months (seen:
"Monthly-IRP-for-August-2026-Subsidized_hd.pdf", "Fuel-Price-Notice-IRP-
May-2026-Subsidized-Prices.pdf", "IRP-Fuel-Price-Notice-08th-July-2026.pdf").

A PDF with no text layer is re-read through ``prices.fetchers.ocr`` (pdftoppm
+ tesseract, already on the collection host). Measured live 2026-09-11, that
recovers the April, May, June and July 2026 notices, which were previously
skipped outright: a full 2025-01-01 rebuild goes from 150 rows to 408.

OCR'd rows get two checks the text-layer path does not need. ``_OCR_ROW_RE``
requires exactly three figures of exactly two decimals, so a dropped cell
fails the match rather than shifting a column. Then ``_drop_off_spread``
checks each centre against the notice's own median product spreads: within one
notice only freight varies by centre, so diesel-petrol and petrol-kerosene are
near-constant down the table (+4.81 and -30.67 toea at 23 of 26 centres on the
08-Jul-2026 notice). That is the check that catches the failure a price cannot
reveal on its own -- OCR read Pogera's petrol as 521.15 where the notice says
511.15, a wholly plausible figure that is only wrong relative to its row-mates.
Measured reject rate: 9 of 95 OCR'd centre-rows (9.5%). The check is
deliberately conservative -- it drops Maprik and Ramu in every notice, and at
least Ramu's kerosene may be a genuine local difference rather than a misread.

Prices are published in toea per litre (100 toea = 1 PGK) -- divided by 100
before emission so `price_local` is in PGK, matching `countries.yaml`'s
currency for Papua New Guinea.

COICOP map (`analytical_role: tariff`, `coicop_classification:
source_curated`), verified against `data/prices/enrich/gold/
coicop_leaves.txt` (the PNG-inventory's original "04.5.4" for kerosene is
NOT a real leaf -- 04.5.4.x is solid fuels, coal/wood/charcoal -- kerosene
is a liquid fuel): Petrol -> 07.2.2.2, Diesel -> 07.2.2.1, Kerosene ->
04.5.3.0 (household lighting/cooking liquid fuel, not vehicle fuel).

`observation_date` / `effective_from` is read from the notice's own
"take effect from ... <date>" sentence when present, falling back to the
date embedded in the post's URL (`/YYYY/MM/DD/...`) otherwise.
"""

from __future__ import annotations

import io
import logging
import re
import statistics
from datetime import date

import pandas as pd
import pdfplumber

from prices.fetchers import ocr
from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Papua New Guinea"
_CURRENCY = "PGK"
_SOURCE_KEY = "pg_iccc_fuel"
_INDEX_URL = "https://iccc.gov.pg/category/monthly-fuel-price/"
_IDENT = ["source_key", "observation_date", "subnational_area", "item_name"]

_COICOP_MAP = {
    "petrol": "07.2.2.2",
    "diesel": "07.2.2.1",
    "kerosene": "04.5.3.0",
}

_POST_HREF_RE = re.compile(
    r'href="(https://iccc\.gov\.pg/(\d{4})/(\d{2})/\d{2}/[^"]+/)"'
)
_PDF_HREF_RE = re.compile(r'href="(https://iccc\.gov\.pg/wp-content/uploads/[^"]+\.pdf)"')

# "       Port Moresby          439.87          444.67          409.20"
_ROW_RE = re.compile(r"^(.+?)\s{2,}([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*$")
_HEADER_RE = re.compile(r"^\s*Centres\b", re.I)
# Layout-preserving text puts 2+ spaces between the centre and its first
# figure; OCR text does not, so the OCR path leans on the shape of the numbers
# instead -- exactly three figures, each with exactly two decimals. A cell OCR
# dropped then fails the match outright rather than shifting the next column's
# price into it.
_OCR_ROW_RE = re.compile(
    r"^(?P<centre>[A-Za-z][^\d]*?)\s+"
    r"(?P<petrol>\d{2,4}\.\d{2})\s+"
    r"(?P<diesel>\d{2,4}\.\d{2})\s+"
    r"(?P<kerosene>\d{2,4}\.\d{2})\s*$"
)
# Within one notice the product spreads are a national excise/subsidy
# structure, not a per-centre one: only freight varies by centre, so
# diesel-petrol and petrol-kerosene are near-constant down the table (measured
# on the 08-Jul-2026 notice: +4.80 and -30.67 at 23 of 26 centres). A centre
# whose spreads miss the notice's own median by more than this is a misread
# digit -- "521.15" for "511.15" reads as a perfectly plausible price on its
# own and is only detectable against its row-mates.
_SPREAD_TOLERANCE_TOEA = 0.5
_EFFECTIVE_RE = re.compile(
    r"take effect from[^,]*,\s*(\d{1,2})(?:st|nd|rd|th)\s+([A-Za-z]+)\s+(\d{4})",
    re.I,
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
_MAX_TOEA = 200_000.0


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


def _parse_pdf_rows(
    content: bytes,
) -> tuple[list[tuple[str, float, float, float]] | None, str]:
    """Return ([(centre, petrol_toea, diesel_toea, kerosene_toea), ...], full_text).
    Rows is None if this PDF has no extractable price table (empty/scanned
    text layer, or a narrative press-statement PDF with no ruled table)."""
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            text = "\n".join(p.extract_text(layout=True) or "" for p in pdf.pages)
    except Exception:
        logger.exception("[%s] could not open PDF", _SOURCE_KEY)
        return None, ""
    from_ocr = False
    if not text.strip() and ocr.ocr_available():
        from_ocr = True
        text = "\n".join(ocr.page_texts(content))
    rows: list[tuple[str, float, float, float]] = []
    pattern = _OCR_ROW_RE if from_ocr else _ROW_RE
    for ln in text.split("\n"):
        m = pattern.match(ln.rstrip())
        if not m:
            continue
        groups = m.groups()
        centre = re.sub(r"\s+", " ", groups[0]).strip(" .|-")
        if not centre or _HEADER_RE.match(centre):
            continue
        try:
            petrol, diesel, kerosene = (float(g) for g in groups[1:4])
        except ValueError:
            continue
        if not all(0 < v <= _MAX_TOEA for v in (petrol, diesel, kerosene)):
            continue
        rows.append((centre, petrol, diesel, kerosene))
    if from_ocr:
        rows = _drop_off_spread(rows)
    return (rows or None), text


def _drop_off_spread(
    rows: list[tuple[str, float, float, float]],
) -> list[tuple[str, float, float, float]]:
    """Drop centres whose product spreads disagree with the notice's own median.

    See _SPREAD_TOLERANCE_TOEA. Needs a real table to take a median from, so
    below 8 centres nothing is dropped and nothing is claimed.
    """
    if len(rows) < 8:
        return rows
    d_spread = statistics.median(d - p for _, p, d, _ in rows)
    k_spread = statistics.median(p - k for _, p, _, k in rows)
    kept = []
    dropped = []
    for centre, petrol, diesel, kerosene in rows:
        if (
            abs((diesel - petrol) - d_spread) > _SPREAD_TOLERANCE_TOEA
            or abs((petrol - kerosene) - k_spread) > _SPREAD_TOLERANCE_TOEA
        ):
            dropped.append(centre)
            continue
        kept.append((centre, petrol, diesel, kerosene))
    if dropped:
        logger.info(
            "[%s] OCR: %d of %d centre(s) dropped -- product spread is off the "
            "notice's own median (diesel-petrol %.2f, petrol-kerosene %.2f): %s",
            _SOURCE_KEY,
            len(dropped),
            len(rows),
            d_spread,
            k_spread,
            ", ".join(dropped),
        )
    return kept


def _rows_from_notice(
    *, rows: list[tuple[str, float, float, float]], eff_date: date, url: str
) -> list[dict]:
    ts = get_scrape_ts()
    out: list[dict] = []
    for centre, petrol, diesel, kerosene in rows:
        for item, toea in (("Petrol", petrol), ("Diesel", diesel), ("Kerosene", kerosene)):
            coicop = _COICOP_MAP.get(item.lower())
            if coicop is None:
                logger.warning("[%s] no COICOP mapping for %s -- dropping row", _SOURCE_KEY, item)
                continue
            record = {
                "observation_date": eff_date.isoformat(),
                "period_kind": "effective_from",
                "country": _COUNTRY,
                "subnational_area": centre,
                "source_key": _SOURCE_KEY,
                "coicop_code": coicop,
                "item_name": item,
                "price_local": round(toea / 100.0, 4),
                "currency": _CURRENCY,
                "unit": "L",
                "source_url": url,
                "notes": (
                    "ICCC Indicative Retail Fuel Price (maximum ceiling, not an "
                    f"observed shelf price). Source published {toea:.2f} toea/litre."
                ),
                "scrape_ts": ts,
                "observation_hash": None,
            }
            record["observation_hash"] = make_hash(record, _IDENT)
            out.append(record)
    return out


def fetch_pg_iccc_fuel(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    try:
        idx = session.get(_INDEX_URL, timeout=60)
        idx.raise_for_status()
    except Exception:
        logger.exception("[%s] could not load %s", _SOURCE_KEY, _INDEX_URL)
        return None

    posts: dict[str, date] = {}
    for m in _POST_HREF_RE.finditer(idx.text):
        url, yyyy, mm = m.group(1), int(m.group(2)), int(m.group(3))
        posts[url] = date(yyyy, mm, 1)  # placeholder, refined per-post below

    if not posts:
        logger.warning("[%s] no monthly fuel-price posts found on %s", _SOURCE_KEY, _INDEX_URL)
        return None

    all_rows: list[dict] = []
    no_table: list[str] = []
    for post_url in sorted(posts):
        try:
            post = session.get(post_url, timeout=60)
            post.raise_for_status()
        except Exception:
            logger.exception("[%s] failed to load post %s", _SOURCE_KEY, post_url)
            continue

        # Cheap pre-check against the post's own URL date -- refined below
        # once/if a PDF's own text yields a more precise effective date.
        m = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", post_url)
        if not m:
            continue
        url_date = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if url_date <= cutoff:
            continue

        pdf_urls = sorted(set(_PDF_HREF_RE.findall(post.text)))
        parsed = None
        used_pdf = None
        pdf_text = ""
        for pdf_url in pdf_urls:
            try:
                resp = session.get(pdf_url, timeout=90)
                resp.raise_for_status()
            except Exception:
                logger.exception("[%s] failed to fetch PDF %s", _SOURCE_KEY, pdf_url)
                continue
            rows, text = _parse_pdf_rows(resp.content)
            if rows and len(rows) >= 5:
                parsed = rows
                used_pdf = pdf_url
                pdf_text = text
                break

        if not parsed:
            no_table.append(post_url)
            continue

        eff_date = (
            _parse_effective_date(pdf_text)
            or _parse_effective_date(post.text)
            or url_date
        )
        if eff_date <= cutoff:
            continue

        notice_rows = _rows_from_notice(rows=parsed, eff_date=eff_date, url=used_pdf)
        logger.info(
            "[%s] %s (%s): %d rows from %s",
            _SOURCE_KEY, post_url, eff_date, len(notice_rows), used_pdf,
        )
        all_rows.extend(notice_rows)

    if no_table:
        logger.warning(
            "[%s] %d of %d post(s) yielded no extractable price table (scanned "
            "PDF or narrative-only; no OCR available): %s",
            _SOURCE_KEY, len(no_table), len(posts), ", ".join(no_table),
        )

    if not all_rows:
        logger.warning("[%s] no rows parsed from %d post(s)", _SOURCE_KEY, len(posts))
        return None

    df = pd.DataFrame(all_rows).drop_duplicates(subset=["observation_hash"])
    return df
