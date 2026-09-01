"""Kyrgyz Republic National Statistical Committee (stat.kg) -- average
consumer prices for selected food goods, published monthly with a
per-city breakdown.

The historical domain www.stat.kg 301-redirects to the canonical
https://stat.gov.kg -- this fetcher requests www.stat.kg and resolves the
document link against the *final* redirected URL (`urljoin`), not a
hardcoded base; hardcoding the old domain as the base for the relative
`/media/files/...` href silently built a URL that read-timed-out instead
of 404ing outright (caught live 2026-09-01).

stat.gov.kg's `/ru/daily-prices/` page ("Мониторинг цен") links two XLS
workbooks by a stable `title=` attribute (the underlying filename is a
random UUID that changes whenever the site re-uploads the file, so the
title is what this fetcher matches on, not the href):
`title="Продовольственные товары"` (food -- this fetcher) and
`title="ГСМ"` (fuel/lubricants -- not scaffolded here, a candidate for a
future narrow `coicop_codes: ["07.2.2"]` source).

The food workbook has one sheet per calendar month back to January 2016
(128 sheets as of 2026-09-01), sheet name `<russian month>_<year>` (e.g.
`август_2026`; several months carry stray trailing whitespace in the
sheet name, e.g. `"июль_2026 "` -- stripped before parsing). Every sheet
shares the same layout, confirmed identical on both the newest
(август_2026, 25 columns) and a decade-old (январь_2016, 26 columns)
sheet: 6 header rows, then repeating 18-row item blocks --
1 item-header row (columns A-C = item name in ky/en/ru, all price columns
NaN) followed by exactly 18 location rows (1 national "Кыргызская
Республика" row + 17 named cities/towns, column C = the ru location
label), then one blank separator row before the next item header.

Each location row's price columns run: [previous month's own average]
[[one column per business day of THIS month]] [this month's own
average] -- column count varies by how many business days the month had,
but position is stable at the two ends. This fetcher extracts ONLY the
last column (this sheet's own month average) as a `period_kind: monthly`
observation -- the first column duplicates the prior sheet's own last
column (would double-count the same month), and the daily columns are
left unscraped as an intentional scope cut (see notes below).

Verified live 2026-09-01: 16 food items per sheet (Пшеница, Рис
среднезернистый, Рис длиннозернистый, ... -- wheat/rice/flour/meat/dairy/
produce staples), 18 locations each, KGS ("сомов за килограмм, литр,
10 штук" -- unit is a blanket per-sheet note, not itemized, so `unit` is
left None here rather than guessed per item).
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date
from urllib.parse import urljoin

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_INDEX_URL = "http://www.stat.kg/ru/daily-prices/"
_COUNTRY = "Kyrgyz Republic"
_CURRENCY = "KGS"
_SOURCE_KEY = "kg_nsc_avg_prices"
_IDENT = ["source_key", "observation_date", "item_name", "subnational_area"]
_NATIONAL_LABEL = "Кыргызская Республика"
_LOCATIONS_PER_ITEM = 18

_DOC_RE = re.compile(
    r'href="(/media/files/[^"]+\.xls)"\s+title="Продовольственные товары"'
)

_RU_MONTHS = {
    "январь": 1,
    "февраль": 2,
    "март": 3,
    "апрель": 4,
    "май": 5,
    "июнь": 6,
    "июль": 7,
    "август": 8,
    "сентябрь": 9,
    "октябрь": 10,
    "ноябрь": 11,
    "декабрь": 12,
}


def _find_doc_url(html: str, base_url: str) -> str | None:
    m = _DOC_RE.search(html)
    if not m:
        return None
    return urljoin(base_url, m.group(1))


def _sheet_month(sheet_name: str) -> date | None:
    parts = sheet_name.strip().split("_")
    if len(parts) != 2:
        return None
    month_ru, year_txt = parts[0].strip().lower(), parts[1].strip()
    month = _RU_MONTHS.get(month_ru)
    if not month or not year_txt.isdigit():
        return None
    return date(int(year_txt), month, 1)


def _parse_sheet(df: pd.DataFrame, obs_date: date, doc_url: str) -> list[dict]:
    ts = get_scrape_ts()
    rows: list[dict] = []
    current_item: str | None = None
    n = len(df)
    i = 6  # first 6 rows are the sheet's own title/unit/column-header block
    while i < n:
        row = df.iloc[i]
        label = row[2]
        rest_nan = row[3:].isna().all()
        if rest_nan:
            # Either a new item header (label present) or the blank
            # separator row between item blocks (label absent).
            current_item = (
                str(label).strip() if isinstance(label, str) and label.strip() else None
            )
            i += 1
            continue
        if (
            current_item is None
            or current_item.startswith("-")
            or "не наблюдается" in current_item.lower()
            or not isinstance(label, str)
            or not label.strip()
        ):
            i += 1
            continue
        location = label.strip()
        subnational_area = None if location == _NATIONAL_LABEL else location
        try:
            price = float(row.iloc[-1])
        except (TypeError, ValueError):
            i += 1
            continue
        # `float(nan)` succeeds (returns nan) and `nan <= 0` is False, so a
        # blank monthly-average cell (a handful of sheets have one, e.g. an
        # item genuinely "not observed" that month) silently passed both
        # guards below and shipped as a NaN price_local row until this
        # explicit isna() check was added -- caught live 2026-09-01 (696
        # NaN rows in the first unbounded run, concentrated in sheets with
        # an irregular footnote row breaking the fixed 18-row item block).
        if pd.isna(price) or price <= 0:
            i += 1
            continue
        out_row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "monthly",
            "country": _COUNTRY,
            "subnational_area": subnational_area,
            "source_key": _SOURCE_KEY,
            "item_name": current_item,
            "price_local": round(price, 4),
            "currency": _CURRENCY,
            "unit": None,
            "source_url": doc_url,
            "notes": f"NSC average consumer price, {location}",
            "scrape_ts": ts,
            "observation_hash": None,
        }
        out_row["observation_hash"] = make_hash(out_row, _IDENT)
        rows.append(out_row)
        i += 1
    return rows


def fetch_kg_nsc_avg_prices(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    try:
        page = session.get(_INDEX_URL, timeout=30)
        page.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] index page fetch failed: %s", _SOURCE_KEY, exc)
        return None

    doc_url = _find_doc_url(page.text, page.url)
    if not doc_url:
        logger.warning(
            "[%s] no matching document link found on index page", _SOURCE_KEY
        )
        return None

    try:
        resp = session.get(doc_url, timeout=120)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] document fetch failed: %s", _SOURCE_KEY, exc)
        return None

    try:
        xl = pd.ExcelFile(io.BytesIO(resp.content))
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] xls parse failed: %s", _SOURCE_KEY, exc)
        return None

    all_rows: list[dict] = []
    for sheet_name in xl.sheet_names:
        obs_date = _sheet_month(sheet_name)
        if obs_date is None or obs_date <= cutoff:
            continue
        try:
            df = xl.parse(sheet_name, header=None)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[%s] failed to parse sheet %r: %s", _SOURCE_KEY, sheet_name, exc
            )
            continue
        sheet_rows = _parse_sheet(df, obs_date, doc_url)
        all_rows.extend(sheet_rows)

    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(all_rows), cutoff)
    return pd.DataFrame(all_rows) if all_rows else None
