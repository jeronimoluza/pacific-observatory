"""ZamStats "The Monthly" bulletin — national average retail prices, Zambia.

The Zambia Statistics Agency (zamstats.gov.zm) publishes a monthly bulletin
("The Monthly", a numbered Volume) that carries, alongside CPI commentary, a
"Table 7: National Average Prices for Selected Products" — a genuine
official average-retail-price series for a fixed basket of ~25 items
(mealie meal, meat cuts, fresh produce, fuel, cement, medicine, etc.),
month-by-month, in ZMW. This is NOT a re-derived CPI index: the table states
raw national average prices with a unit of measure per item. Re-verified
live 2026-09-01 against Volume 281 (August 2026): 25 items, e.g. "Mixed Cut
1 Kg" ZMW 106.53, "Diesel 1 Ltr" ZMW 26.86, "Tomatoes 1 Kg" ZMW 16.35 —
plausible ZMW magnitudes matching countries.yaml.

The onboarding brief named this "average retail prices for a food basket by
PROVINCE" — that dataset was NOT found in this bulletin (Table 7 is a
national aggregate only; Table 1.4 nearby is CPI *by province*, an index,
not average prices). This fetcher ships what was actually verified live:
the national Table 7 series. Recorded here so a later run does not
re-search for a provincial average-price table that may not exist.

DISCOVERY: the bulletin's WordPress post slug embeds the release month
(`monthly-inflation-<month>-<year>`, e.g. `monthly-inflation-august-2026`)
and is not predictable in advance (some months are `annual-inflation-...`
instead, or double-barrelled `<month>-<year>-<month>-<year>` for spliced
annual/monthly issues). Rather than guess the slug, this fetcher queries
the site's open WP REST API (`/wp-json/wp/v2/posts?search=Monthly`, no
auth) sorted by date desc, takes the newest post whose slug starts with
`monthly-inflation-`, and extracts the first `.pdf` link from its rendered
content — confirmed live 2026-09-01: resolves straight to
`.../Vol-281-of-2026-The-Monthly-August-1.pdf`. Note: searching the
literal hyphenated string "monthly-inflation" (WP fulltext search does
not match slugs) returns a DIFFERENT, incomplete result set that omits
the true latest post — confirmed live: it silently returned an April-2026
bulletin as "latest" while a plain "Monthly" search correctly surfaced
August-2026. Search on a real word, not a slug fragment.

PDF TABLE PARSING: pdfplumber's text extraction wraps each item's
multi-word description across 1-3 physical lines (the numeric columns only
render on the FIRST line of each item block; continuation lines carry only
description/UOM fragments). This fetcher detects a "numeric line" as
`<description prefix> <12 monthly values> <2 inflation deltas>` and folds
any following non-numeric lines into that item's description. The resulting
`item_name` is occasionally out of natural word order (PDF column-wrap
artifact, e.g. "Sweet 1 Kg potatoes" for "Sweet potatoes, 1 Kg") but is
never fabricated — every token comes from the source PDF. Left to the
classifier rather than hand-cleaned, per the "don't normalise the raw name"
convention.

Only the LATEST month's column (rightmost of the 12) is emitted per run —
each bulletin covers a 12-month trailing window with heavy overlap
month-to-month, so re-running monthly accumulates the full series without
re-parsing 12 overlapping columns every time; the standard cutoff filter
below (`observation_date > cutoff`) makes this idempotent regardless.

analytical_role: official_avg -> PriceObservation, not IndexObservation.
coicop_classification: classifier — the basket spans food (division 01),
transport fuel (07), housing materials (04/05), health (06), and personal
care (12); no single COICOP class covers it (wide, not narrow).
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

_COUNTRY = "Zambia"
_SOURCE_KEY = "zamstats_avg_prices"
_CURRENCY = "ZMW"
_POSTS_API = "https://www.zamstats.gov.zm/wp-json/wp/v2/posts"
_IDENT = ["source_key", "observation_date", "item_name"]

_PDF_RE = re.compile(r'href="([^"]+\.pdf)"', re.IGNORECASE)
_TABLE_HEADING = "Table 7: National Average Prices"
_ROW_RE = re.compile(r"^(?P<desc>.*?)\s+(?P<nums>(?:\(?-?[\d,]+\.\d{2}\)?\s*){10,})$")
_MONTH_RE = re.compile(
    r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{4})$",
    re.IGNORECASE,
)


def _find_latest_bulletin_pdf(session) -> tuple[str, str] | None:
    """Return (pdf_url, post_slug) for the newest 'monthly-inflation-*' post."""
    try:
        resp = session.get(
            _POSTS_API,
            params={
                "search": "Monthly",
                "orderby": "date",
                "order": "desc",
                "per_page": 20,
            },
            timeout=30,
        )
        resp.raise_for_status()
        posts = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] wp-json posts lookup failed: %s", _SOURCE_KEY, exc)
        return None

    for post in posts:
        slug = post.get("slug", "")
        if not slug.startswith("monthly-inflation-"):
            continue
        content = post.get("content", {}).get("rendered", "")
        m = _PDF_RE.search(content)
        if m:
            return m.group(1), slug
    return None


def _slug_to_period(slug: str) -> str | None:
    """'monthly-inflation-august-2026' -> '2026-08-01'. Uses the LAST
    month-year pair in the slug (double-barrelled slugs report the most
    recent month last, e.g. 'monthly-inflation-april-2024-april-2025')."""
    months = {
        m: i + 1
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
            ]
        )
    }
    parts = slug.replace("monthly-inflation-", "").split("-")
    found = None
    for i in range(len(parts) - 1):
        mon = parts[i].lower()
        if mon in months and parts[i + 1].isdigit() and len(parts[i + 1]) == 4:
            found = (int(parts[i + 1]), months[mon])
    if not found:
        return None
    year, month = found
    return date(year, month, 1).isoformat()


def _extract_table7_rows(pdf_bytes: bytes) -> list[tuple[str, float]]:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        target_text = None
        for p in pdf.pages:
            t = p.extract_text() or ""
            if _TABLE_HEADING in t:
                target_text = t
                break
    if not target_text:
        return []

    lines = target_text.split("\n")
    start = next(
        (
            i + 1
            for i, line in enumerate(lines)
            if line.strip().startswith("Aug 25")
            or re.match(r"^[A-Za-z]{3} \d{2}\s", line.strip())
        ),
        None,
    )
    if start is None:
        return []
    end = next(
        (i for i, line in enumerate(lines) if line.strip().startswith("Source:")),
        len(lines),
    )
    lines = lines[start:end]

    rows: list[tuple[str, float]] = []
    i = 0
    while i < len(lines):
        m = _ROW_RE.match(lines[i].strip())
        if m:
            desc_parts = [m.group("desc").strip()]
            nums = m.group("nums").split()
            i += 1
            while (
                i < len(lines)
                and lines[i].strip()
                and not _ROW_RE.match(lines[i].strip())
            ):
                desc_parts.append(lines[i].strip())
                i += 1
            if len(nums) >= 3:
                # last 2 tokens are Mth's/Yr's inflation deltas; the one
                # before that is the latest (rightmost) monthly value.
                try:
                    latest_val = float(nums[-3].replace(",", ""))
                except ValueError:
                    continue
                name = " ".join(p for p in desc_parts if p)
                rows.append((name, latest_val))
        else:
            i += 1
    return rows


def fetch_zamstats_avg_prices(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    found = _find_latest_bulletin_pdf(session)
    if not found:
        logger.warning("[%s] could not resolve latest bulletin post", _SOURCE_KEY)
        return None
    pdf_url, slug = found

    obs_date = _slug_to_period(slug)
    if not obs_date:
        logger.warning("[%s] could not parse period from slug %r", _SOURCE_KEY, slug)
        return None
    if date.fromisoformat(obs_date) <= cutoff:
        logger.info(
            "[%s] latest bulletin (%s) is at/before cutoff=%s",
            _SOURCE_KEY,
            obs_date,
            cutoff,
        )
        return None

    try:
        resp = session.get(pdf_url, timeout=60)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] pdf fetch failed: %s", _SOURCE_KEY, exc)
        return None

    items = _extract_table7_rows(resp.content)
    if not items:
        logger.warning("[%s] no rows parsed from Table 7 in %s", _SOURCE_KEY, pdf_url)
        return None

    ts = get_scrape_ts()
    rows = []
    for name, price in items:
        if price <= 0:
            continue
        row = {
            "observation_date": obs_date,
            "period_kind": "monthly",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": name,
            "price_local": round(price, 4),
            "currency": _CURRENCY,
            "unit": None,
            "source_url": pdf_url,
            "notes": "ZamStats 'The Monthly' bulletin, Table 7 (national average, latest month column)",
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    logger.info(
        "[%s] %d rows for %s (cutoff=%s)", _SOURCE_KEY, len(rows), obs_date, cutoff
    )
    return pd.DataFrame(rows) if rows else None
