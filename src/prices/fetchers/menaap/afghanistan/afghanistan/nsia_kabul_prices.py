"""Afghanistan National Statistics and Information Authority (NSIA) --
weekly average retail prices for ~50 food and non-food items in Kabul city.

The public-facing `nsia.gov.af` is an Angular SPA with no price endpoint.
The publications actually live on a WordPress instance at
`gsia.gov.af:8443`, whose REST media index enumerates every published file:

    GET https://gsia.gov.af:8443/index.php/wp-json/wp/v2/media
        ?search=<Dari "قلم" = "item">&per_page=100&page=N

**`verify=False` is required.** The host serves an incomplete certificate
chain, so a verifying client fails the handshake outright; there is no
alternative hostname that works. Verification is disabled for this host
only, and urllib3's resulting warning is suppressed locally rather than
globally.

201 media rows match, of which 118 are XLSX workbooks titled
"اوسط قیمت 50 قلم شهر کابل بابت هفته ..." ("average price of 50 items,
Kabul city, for the week of ..."). Their filenames carry an Afghan solar
Hijri week label (e.g. "هفته اول سنبله ۱۴۰۵" = first week of Sunbula 1405),
which is why the file name is NOT used to date the observation.

DATING: the survey week is read out of the workbook's own English title,
NOT off the filename and NOT off the publication date. Every one of the
115 readable workbooks carries a line of the form "Kabul City Food and
Non-Food Items Weekly Average Prices For <First|Second|Third|Fourth|Last>
[Week] of <Month> <Year>", so the week ordinal maps to a day-of-month
(1st->01, 2nd->08, 3rd->15, 4th->22, Last->29) and gives a real, ordered
observation date.

The publication date was tried first and is wrong: 118 workbooks share
only 90 distinct publication dates -- NSIA regularly uploads two survey
weeks on one day (e.g. "Third Week of July 2024" and "Fourth Week of July
2024" were both published 2024-08-01) -- which collapsed 1,228 of 5,672
rows onto colliding `observation_hash` values. The publication date
survives only as a fallback for a workbook whose title will not parse, and
as a cheap pre-filter: a title date never trails its publication by more
than about five weeks, so the fetcher only downloads workbooks published
after `cutoff - 45 days` and then re-filters exactly on the parsed title
date. Rows are de-duplicated on `observation_hash` before returning,
because the writer only de-dupes a new batch against what is already on
disk, not against itself.

Workbook layout, verified identical on files published 2025-01-05,
2025-11-24 and 2026-08-30 (58 rows x 15 columns, single sheet): a title
block, then a two-tier header whose English tier names the columns
`Previews Year | Previews Month | Previews Week` (percent changes) and
`Current Week | Previews Week | Previews Month` (average prices in
afghani), then ~50 item rows with `No | Items | Unit | Quality`. Column
indices are NOT hardcoded -- the parser locates the header row by the
literal "Current Week" and the label row by "Items", so a re-ordered
workbook degrades to a logged skip instead of silently mis-columned rows.

Only the "Current Week" price is emitted. The "Previews Week"/"Previews
Month" columns restate observations that the preceding workbooks already
carry, and emitting them would duplicate rows under a different date.

Roughly items 1-33 of 50 are COICOP division 01/02 (rice, wheat flour,
buffalo/veal/mutton/chicken, milk powder, liquid milk, eggs, vegetable
oil, fruit, vegetables, pulses, sugar, tea, soft drinks); the tail is
housing fuel, personal care and household goods. No alcohol and no
tobacco, as expected for Afghanistan. Item names are English, so
`language: en`, and the leading apostrophes Excel leaves on a few of them
("'Egg", "'High Quality Thin Rice") are stripped.

The 2020-era files under the same search term are a different, older
format that pandas cannot open ("Excel file format cannot be determined")
-- they are skipped with a warning rather than special-cased.
"""

from __future__ import annotations

import io
import logging
import warnings
import re
from datetime import date, datetime, timedelta

import pandas as pd
import urllib3

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_MEDIA_URL = (
    "https://gsia.gov.af:8443/index.php/wp-json/wp/v2/media"
    "?search=%D9%82%D9%84%D9%85&per_page=100&page={page}"
)
_MAX_PAGES = 10
_COUNTRY = "Afghanistan"
_CURRENCY = "AFN"
_SOURCE_KEY = "af_nsia_kabul_prices"
_AREA = "Kabul"
_IDENT = ["source_key", "observation_date", "item_name", "subnational_area"]

# A title date never trails its publication date by more than ~5 weeks;
# this window keeps incremental runs from re-downloading the whole archive
# while still catching every workbook that could carry a new survey week.
_PUBLISH_GRACE = timedelta(days=45)

_TITLE_DATE_RE = re.compile(
    r"\b(first|second|third|fourth|fifth|last)\b(?:\s+week)?\s+of\s+"
    r"(january|february|march|april|may|june|july|august|september|october|"
    r"november|december)\b.*?\b(20\d{2})\b",
    re.IGNORECASE,
)
_WEEK_DAY = {
    "first": 1,
    "second": 8,
    "third": 15,
    "fourth": 22,
    "fifth": 29,
    "last": 29,
}
_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

_PRICE_HEADER = "current week"
_LABEL_ITEMS = "items"
_LABEL_UNIT = "unit"
_LABEL_QUALITY = "quality"


def _media_items(session) -> list[tuple[date, str]]:
    """`[(published_date, xlsx_url), ...]`, newest first."""
    out: list[tuple[date, str]] = []
    page = 1
    total_pages = 1
    while page <= min(total_pages, _MAX_PAGES):
        try:
            resp = session.get(_MEDIA_URL.format(page=page), timeout=120, verify=False)
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] media page %d failed: %s", _SOURCE_KEY, page, exc)
            break
        try:
            total_pages = int(resp.headers.get("X-WP-TotalPages", "1"))
        except ValueError:
            total_pages = 1
        try:
            payload = resp.json()
        except ValueError:
            logger.warning("[%s] media page %d not JSON", _SOURCE_KEY, page)
            break
        if not isinstance(payload, list):
            break
        for entry in payload:
            url = (entry or {}).get("source_url") or ""
            if not url.lower().endswith((".xlsx", ".xls")):
                continue
            raw_date = (entry or {}).get("date") or ""
            try:
                published = datetime.fromisoformat(raw_date).date()
            except ValueError:
                continue
            out.append((published, url))
        page += 1
    return out


def _cell(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip().lstrip("'").strip()


def _locate(df: pd.DataFrame) -> tuple[int, int, int, int, int] | None:
    """`(header_row, price_col, items_col, unit_col, quality_col)`."""
    header_row = price_col = None
    for i in range(min(20, len(df))):
        for j, value in enumerate(df.iloc[i].tolist()):
            if _PRICE_HEADER in _cell(value).lower():
                header_row, price_col = i, j
                break
        if header_row is not None:
            break
    if header_row is None:
        return None

    items_col = unit_col = quality_col = None
    for i in range(header_row + 1):
        for j, value in enumerate(df.iloc[i].tolist()):
            label = _cell(value).lower()
            if label == _LABEL_ITEMS and items_col is None:
                items_col = j
            elif label == _LABEL_UNIT and unit_col is None:
                unit_col = j
            elif label == _LABEL_QUALITY and quality_col is None:
                quality_col = j
    if items_col is None:
        return None
    return header_row, price_col, items_col, unit_col, quality_col


def _english_title(df: pd.DataFrame) -> str | None:
    for value in df.iloc[: min(8, len(df))].to_numpy().ravel():
        text = _cell(value)
        if "Kabul" in text and "Price" in text:
            return " ".join(text.split())
    return None


def _title_date(title: str | None) -> date | None:
    """Survey week from the workbook's English title, e.g. 'Third Week of
    November 2025' -> 2025-11-15."""
    if not title:
        return None
    m = _TITLE_DATE_RE.search(title)
    if not m:
        return None
    day = _WEEK_DAY[m.group(1).lower()]
    month = _MONTHS[m.group(2).lower()]
    year = int(m.group(3))
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _parse_workbook(content: bytes, published: date, url: str) -> list[dict]:
    try:
        book = pd.ExcelFile(io.BytesIO(content))
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] unreadable workbook %s: %s", _SOURCE_KEY, url, exc)
        return []
    df = book.parse(book.sheet_names[0], header=None)

    located = _locate(df)
    if located is None:
        logger.warning("[%s] header not found in %s", _SOURCE_KEY, url)
        return []
    header_row, price_col, items_col, unit_col, quality_col = located

    title = _english_title(df)
    obs_date = _title_date(title) or published
    if obs_date is published:
        logger.warning(
            "[%s] unparseable title in %s -- falling back to publication date %s",
            _SOURCE_KEY,
            url,
            published,
        )
    note = "NSIA Kabul weekly average retail price"
    if title:
        note = f"{note}; workbook title: {title}"

    ts = get_scrape_ts()
    rows: list[dict] = []
    seen: set[str] = set()
    for i in range(header_row + 1, len(df)):
        record = df.iloc[i]
        item = _cell(record.iloc[items_col]) if items_col < len(record) else ""
        if not item:
            continue
        if price_col >= len(record):
            continue
        try:
            price = float(record.iloc[price_col])
        except (TypeError, ValueError):
            continue
        if pd.isna(price) or price <= 0:
            continue
        quality = (
            _cell(record.iloc[quality_col])
            if quality_col is not None and quality_col < len(record)
            else ""
        )
        unit = (
            _cell(record.iloc[unit_col])
            if unit_col is not None and unit_col < len(record)
            else ""
        )
        item_name = f"{item} ({quality})" if quality else item
        if item_name in seen:
            continue
        seen.add(item_name)
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "weekly_avg",
            "country": _COUNTRY,
            "subnational_area": _AREA,
            "source_key": _SOURCE_KEY,
            "item_name": item_name[:300],
            "price_local": round(price, 4),
            "currency": _CURRENCY,
            "unit": unit or None,
            "source_url": url,
            "notes": note,
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)
    return rows


def fetch_af_nsia_kabul_prices(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", urllib3.exceptions.InsecureRequestWarning)
        media = _media_items(session)
        if not media:
            logger.warning("[%s] no media entries returned", _SOURCE_KEY)
            return None
        pending = [(d, u) for d, u in media if d > cutoff - _PUBLISH_GRACE]
        logger.info(
            "[%s] %d workbooks listed, %d published after cutoff %s - %d days",
            _SOURCE_KEY,
            len(media),
            len(pending),
            cutoff,
            _PUBLISH_GRACE.days,
        )

        all_rows: list[dict] = []
        for published, url in pending:
            try:
                resp = session.get(url, timeout=180, verify=False)
                resp.raise_for_status()
            except Exception as exc:  # noqa: BLE001
                logger.warning("[%s] download failed %s: %s", _SOURCE_KEY, url, exc)
                continue
            rows = _parse_workbook(resp.content, published, url)
            # The grace window admits workbooks whose survey week is already
            # banked; the exact filter is on the parsed title date.
            rows = [r for r in rows if r["observation_date"] > cutoff.isoformat()]
            if rows:
                logger.info(
                    "[%s] %s -> %d rows", _SOURCE_KEY, rows[0]["observation_date"], len(rows)
                )
            all_rows.extend(rows)

    if not all_rows:
        logger.info("[%s] 0 rows (cutoff=%s)", _SOURCE_KEY, cutoff)
        return None

    df = pd.DataFrame(all_rows)
    before = len(df)
    # The writer de-dupes a new batch against what is on disk, not against
    # itself -- two workbooks can still restate one survey week.
    df = df.drop_duplicates(subset="observation_hash", keep="first")
    logger.info(
        "[%s] %d rows (cutoff=%s, %d in-batch duplicates dropped)",
        _SOURCE_KEY,
        len(df),
        cutoff,
        before - len(df),
    )
    return df
