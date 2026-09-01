"""Guyana Bureau of Statistics -- monthly Consumer Price Index (Georgetown).

The subject-taxonomy listing page at `_LISTING_URL` returns every monthly CPI
release post in one page load (no pagination observed: a single GET returned
83 distinct month/year posts spanning March 2019 - July 2026) -- confirmed by
diffing the extracted (year, month) set against a manual count. Post slugs
are irregular across the archive (verified live 2026-09-01): most are
`consumer-price-index-georgetown-guyana-<month>-<year>`, some early ones drop
"guyana" (`consumer-price-index-georgetown-<month>-<year>`), a few glue month
and year with no hyphen (`...-february2022`), and a handful of re-published
pages carry a `-2` suffix (`...-may-2020-2`). The regex normalizes all of
these to a (month, year) key and de-dupes.

Each post embeds the release as ONE `supsystic-table` HTML table (parses
cleanly with `pandas.read_html`, no OCR/PDF involved) with 9 fixed group rows
("ALL ITEMS" plus Roman numerals I-IX) and a variable number of leading
year-over-year trend columns (December snapshots) whose count grows every
year, PLUS a variable number of trailing "% Change" columns (2 in most
releases, but 3 in March 2019 -- verified by hand). A fixed-position rule
("3rd-from-last column") silently picks up the wrong column on releases with
3 trailing %-change columns, so the parser instead locates the
current-period column by matching header text against the release's own
month/year (e.g. "MAR 2019", or "JUL"+"2026" split across two header rows in
the 2026-era table redesign -- both layouts verified live). The header
region is bounded by the "ALL ITEMS" row (the first content row); every row
above it, concatenated per column, is searched for the target month+year
token.

Guyana's classification is a legacy 9-group scheme, coarser than COICOP-2018
in two places and finer in one:
  I    FOOD                                        -> 01
  II   CLOTHING                                    -> 03.1 (COICOP splits
  III  FOOTWEAR AND REPAIRS                        -> 03.2  03 into these
                                                        two sub-classes)
  IV   HOUSING                                     -> 04
  V    FURNITURE                                   -> 05
  VI   TRANSPORT & COMMUNICATION                   -> 07  (bundles Transport
                                                        AND Communication;
                                                        Guyana does not break
                                                        these out separately,
                                                        so 08 is not covered
                                                        by this source)
  VII  MEDICAL CARE AND HEALTH SERVICES            -> 06
  VIII EDUCATION, RECREATION & CULTURAL SERVICES   -> 10  (bundles Education
                                                        AND Recreation/Culture;
                                                        09 is not covered by
                                                        this source)
  IX   MISCELLANEOUS GOODS & SERVICES              -> 13
ALL ITEMS (headline, all-items index) is dropped -- no sanctioned sentinel
for it in IndexObservation yet (see the skill's open design question).

Item-label casing varies release-to-release ("FOOD" vs "Food", "SEVICES"
typo present in every observed year) -- matched case-insensitively with the
misspelling as an explicit alias, not fixed at match time.

Six releases needed extra handling beyond the header-token match (all
confirmed live, 2026-09-01):
  - Jul/Aug/Sep 2022 and Sep 2024: the col-1 header cell itself reads "ALL
    ITEMS" instead of "Item"/"Items" (a publisher typo), which falsely
    matches the "first content row" search if it starts from row 0. Fixed
    by anchoring the search to start after the row whose col-0 cell reads
    "Group".
  - Sep 2024/2025: "September" is abbreviated "SEPT" (4 letters), not the
    "SEP" every other month uses.
  - Jul 2025: the release's own trend-column headers are mislabeled (DEC...,
    JUN, MAY, JUN instead of DEC..., JUL, JUN, JUL) -- a genuine publisher
    error, not a parsing artifact; no header cell on that page reads "JUL
    2025" anywhere. Falls back to position: current period is always the
    column immediately before the trailing "%"/"INFLATION" ratio columns.
    Cross-checked against the July 2026 release's own "JUL 2025" historical
    column (FOOD 225.50 both ways) before trusting the fallback.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_LISTING_URL = "https://statisticsguyana.gov.gy/subjects/price-indices/"
_COUNTRY = "Guyana"
_SOURCE_KEY = "gy_statisticsguyana_cpi"
_BASE_PERIOD = "Dec2009=100"
_IDENT = ["source_key", "observation_date", "coicop_code"]

_MONTH_NUM = {
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

# Item-label (lowercased, stripped) -> COICOP code. "sevices" is the
# publisher's own typo for "services", present in every sampled year.
_GROUP_TO_COICOP = {
    "food": "01",
    "clothing": "03.1",
    "footwear and repairs": "03.2",
    "housing": "04",
    "furniture": "05",
    "transport & communication": "07",
    "medical care and health services": "06",
    "education, recreation & cultural services": "10",
    "miscellaneous goods & services": "13",
    "miscellaneous goods & sevices": "13",
}

_POST_RE = re.compile(
    r'href="(https?://statisticsguyana\.gov\.gy/subjects/price-indices/'
    r"consumer-price-index-georgetown(?:-guyana)?-"
    r"(january|february|march|april|may|june|july|august|september|october|november|december)"
    r"-?(\d{4})(?:-\d)?/?)\"",
    re.IGNORECASE,
)


def _find_posts(session) -> list[tuple[str, date]]:
    resp = session.get(_LISTING_URL, timeout=30)
    resp.raise_for_status()
    by_period: dict[tuple[int, int], str] = {}
    for href, month_name, year in _POST_RE.findall(resp.text):
        month = _MONTH_NUM[month_name.lower()]
        by_period[(int(year), month)] = href
    return [(url, date(y, m, 1)) for (y, m), url in sorted(by_period.items())]


def _target_tokens(obs_date: date) -> set[str]:
    month_abbr = obs_date.strftime("%b")  # "Jan".."Dec"
    tokens = {f"{month_abbr}{obs_date.year}".lower()}
    if obs_date.month == 9:
        # Some releases (e.g. September 2024) spell September as "SEPT",
        # not the standard 3-letter "SEP" every other month uses.
        tokens.add(f"sept{obs_date.year}")
    return tokens


def _parse_release(html: str, obs_date: date) -> list[tuple[str, float]]:
    tables = pd.read_html(io.StringIO(html))
    if not tables:
        return []
    df = tables[0]
    if df.shape[1] < 4:
        return []

    # The "ALL ITEMS" row is the first content row; every row above it is
    # header material (title, and either a combined "MON YEAR" row or a
    # split month-row + year-row, depending on table-redesign era). Search
    # for "all items" only AFTER the "Group" header-label row: 6 releases
    # (e.g. July 2022) have a publisher typo where the col-1 header cell
    # itself reads "ALL ITEMS" instead of "Item"/"Items", which falsely
    # matches if the search starts from row 0.
    group_label_idx = None
    for i in range(len(df)):
        v = df.iloc[i, 0]
        if isinstance(v, str) and v.strip().lower() == "group":
            group_label_idx = i
            break
    search_start = group_label_idx + 1 if group_label_idx is not None else 0

    first_content_idx = None
    for i in range(search_start, len(df)):
        v = df.iloc[i, 1]
        if isinstance(v, str) and v.strip().lower() == "all items":
            first_content_idx = i
            break
    if first_content_idx is None:
        return []
    header_rows = df.iloc[0:first_content_idx]

    def _col_text(c: int) -> str:
        return "".join(
            str(x)
            for x in header_rows.iloc[:, c]
            if isinstance(x, str) or (isinstance(x, (int, float)) and not pd.isna(x))
        )

    targets = _target_tokens(obs_date)
    value_col = None
    for c in range(2, df.shape[1]):
        text_norm = re.sub(r"[\s.]", "", _col_text(c)).lower()
        if text_norm in targets:
            value_col = c
            break

    if value_col is None:
        # July 2025's own release mislabels its trend-column headers (a
        # publisher typo -- confirmed against the July 2026 release's "JUL
        # 2025" historical column, which carries the identical value), so no
        # header text on that page reads "JUL 2025" anywhere. Fall back to
        # position: the current period is always immediately before the
        # trailing "% Change"/"INFLATION" ratio columns, regardless of what
        # its own header says.
        ratio_cols = [
            c
            for c in range(2, df.shape[1])
            if "%" in _col_text(c) or "inflation" in _col_text(c).lower()
        ]
        if ratio_cols:
            value_col = min(ratio_cols) - 1
    if value_col is None:
        return []

    out = []
    for i in range(first_content_idx, df.shape[0]):
        item_raw = df.iloc[i, 1]
        if not isinstance(item_raw, str):
            continue
        key = item_raw.strip().lower()
        coicop = _GROUP_TO_COICOP.get(key)
        if coicop is None:
            continue  # "ALL ITEMS" (dropped) or a non-data row (title/footer)
        try:
            val = float(df.iloc[i, value_col])
        except (TypeError, ValueError):
            continue
        out.append((coicop, val))
    return out


def fetch_gy_statisticsguyana_cpi(cutoff: date) -> pd.DataFrame | None:
    session = get_session()

    try:
        posts = _find_posts(session)
    except Exception:
        logger.exception(
            "[%s] Failed to list releases from %s", _SOURCE_KEY, _LISTING_URL
        )
        return None

    if not posts:
        logger.warning(
            "[%s] No CPI release posts found on %s", _SOURCE_KEY, _LISTING_URL
        )
        return None

    rows = []
    for post_url, obs_date in posts:
        if obs_date <= cutoff:
            continue
        try:
            resp = session.get(post_url, timeout=30)
            resp.raise_for_status()
            parsed = _parse_release(resp.text, obs_date)
        except Exception:
            logger.exception("[%s] Failed to parse %s", _SOURCE_KEY, post_url)
            continue
        if not parsed:
            logger.warning("[%s] No group rows parsed from %s", _SOURCE_KEY, post_url)
            continue
        for coicop, idx_val in parsed:
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "monthly_avg",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": coicop,
                "index_value": idx_val,
                "index_base_period": _BASE_PERIOD,
                "source_url": post_url,
                "scrape_ts": get_scrape_ts(),
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    return pd.DataFrame(rows) if rows else None
