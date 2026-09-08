"""Papua New Guinea Independent Consumer & Competition Commission (ICCC) --
monthly Indicative Retail Fuel Price (IRP) notices.

ICCC publishes a press-release post roughly once a month at
https://iccc.gov.pg/category/monthly-fuel-price/ announcing the maximum
indicative retail price for Petrol, Diesel and Kerosene at ~25 named centres
across PNG. Each post links one or more PDFs; only some vintages carry a
text layer (others are scanned images with no OCR available in this
environment, matching the same population found on Kiribati's MCIC price
orders). The fetcher tries every PDF linked from a post and keeps whichever
one parses into rows -- it does not trust the filename to identify "the"
price-table PDF, because naming is inconsistent across months (seen:
"Monthly-IRP-for-August-2026-Subsidized_hd.pdf", "Fuel-Price-Notice-IRP-
May-2026-Subsidized-Prices.pdf", "IRP-Fuel-Price-Notice-08th-July-2026.pdf"
-- the last of which, like the March/April/June IRP PDFs, has NO extractable
text at all).

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
from datetime import date

import pandas as pd
import pdfplumber

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
    rows: list[tuple[str, float, float, float]] = []
    for ln in text.split("\n"):
        m = _ROW_RE.match(ln.rstrip())
        if not m:
            continue
        centre = re.sub(r"\s+", " ", m.group(1)).strip()
        if not centre or _HEADER_RE.match(centre):
            continue
        try:
            petrol, diesel, kerosene = (float(m.group(i)) for i in (2, 3, 4))
        except ValueError:
            continue
        if not all(0 < v <= _MAX_TOEA for v in (petrol, diesel, kerosene)):
            continue
        rows.append((centre, petrol, diesel, kerosene))
    return (rows or None), text


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
