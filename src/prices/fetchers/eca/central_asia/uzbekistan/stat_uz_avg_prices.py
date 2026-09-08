"""Uzbekistan National Statistics Committee (stat.uz) -- monthly average
observed prices for selected food commodities on farmers' markets, national
plus one series per region.

Discovery: the Russian-language "Цены и индексы" official-statistics page
lists every dataset as a trio of SDMX export links
(`.csv` / `.xlsx` / `.pdf`) served from `api.siat.stat.uz`, with the dataset
title rendered immediately before the links. This fetcher parses that page
and keeps only the datasets whose title matches
"Динамика средних цен на отдельные товары на ... рынках", i.e. ONE venue
scope (markets). The two sibling national series it deliberately skips are
"...на рынках и в магазинах" (markets AND shops) and "...в магазинах"
(shops) -- they cover the same 41 items and the same months, so pulling all
three would emit three different prices under one identical
(item_name, observation_date, subnational_area) key and collide on
`observation_hash`. Venue is not a column in PRICE_COLUMNS, so the safe move
is to pick one venue and say so.

Kept, as of 2026-09-05:
  - 1327  national, "на рынках"                     -> subnational_area None
  - 3771..3784  one per region, "на дехканских рынках <Region>"
                                                    -> subnational_area set

The dataset ids are NOT hardcoded: they are read off the index page each
run, because the SDMX export ids change when the committee re-publishes a
table.

CSV shape (verified live 2026-09-05, identical across all 15 files): a wide
matrix, 5 label columns
(`Code`, `Klassifikator` uz-latin, `Klassifikator_ru`, `Klassifikator_en`,
`Klassifikator_uzc` uz-cyrillic) followed by one column per month. 41-42
commodity rows, 163 monthly columns spanning 2013-M01 to 2026-M07.

Two parsing traps in that header, both live in the same file:
  1. The month marker is sometimes the CYRILLIC letter М (U+041C) and
     sometimes the LATIN M -- e.g. `2021-М01` but `2022-M01`. The period
     regex accepts both.
  2. Missing observations are written as `0.0`, not as a blank -- an item
     the committee did not observe in a given month (or before the series
     started for that item) reads as a real zero price. Zeros are dropped.

Item names are emitted in Russian (`Klassifikator_ru`) to match the
manifest's `language: ru`; the English label and the venue/region are
carried in `notes`. Units are not itemised by the publisher -- they are
embedded in some item names ("Молоко свежее (1 литр)", "Яйца (10 штук)")
and implicitly per-kilogram otherwise -- so `unit` is left None rather than
guessed, same treatment as the sibling `kg_nsc_avg_prices` fetcher.
"""

from __future__ import annotations

import csv
import io
import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_INDEX_URL = "https://stat.uz/ru/ofitsialnaya-statistika/prices-and-indexes"
_CSV_URL = "https://api.siat.stat.uz/media/uploads/sdmx/sdmx_data_{id}.csv"
_COUNTRY = "Uzbekistan"
_CURRENCY = "UZS"
_SOURCE_KEY = "uz_stat_avg_prices"
_IDENT = ["source_key", "observation_date", "item_name", "subnational_area"]

_CSV_LINK_RE = re.compile(r"sdmx_data_(\d+)\.csv")
_TAG_TEXT_RE = re.compile(r">([^<>]{15,200})<")
# "на рынках" / "на дехканских рынках <Region>", but NOT the
# "...и в магазинах" / "...в магазинах" siblings (different venue scope).
# The negative lookahead on "магазин" is load-bearing: without it the
# trailing `[^<>]*` happily swallows " и в магазинах" out of the
# markets-AND-shops title and ships it as a bogus `subnational_area`
# (caught on the first live run -- 2,741 junk rows).
_MARKET_TITLE_RE = re.compile(
    r"Динамика средних цен на отдельные товары на\s+"
    r"(?:дехканских\s+)?рынках\s*(?P<area>[^<>]*)$"
)
_SHOPS_RE = re.compile(r"магазин", re.IGNORECASE)
# Accepts both the Cyrillic М (U+041C) and the Latin M used in the header.
_PERIOD_RE = re.compile(r"^(\d{4})-[MМ](\d{2})$")


def _discover_datasets(html: str) -> list[tuple[str, str | None, str]]:
    """`[(dataset_id, subnational_area, title), ...]` for the market series.

    The dataset title is the last text node before its export links, so we
    look backwards from each `sdmx_data_<id>.csv` occurrence.
    """
    out: list[tuple[str, str | None, str]] = []
    seen: set[str] = set()
    for m in _CSV_LINK_RE.finditer(html):
        ds_id = m.group(1)
        if ds_id in seen:
            continue
        window = html[max(0, m.start() - 1500) : m.start()]
        texts = [t.strip() for t in _TAG_TEXT_RE.findall(window) if t.strip()]
        if not texts:
            continue
        title = texts[-1]
        if _SHOPS_RE.search(title):
            continue
        hit = _MARKET_TITLE_RE.match(title)
        if not hit:
            continue
        seen.add(ds_id)
        area = hit.group("area").strip() or None
        out.append((ds_id, area, title))
    return out


def _period_to_date(label: str) -> date | None:
    m = _PERIOD_RE.match(label.strip())
    if not m:
        return None
    year, month = int(m.group(1)), int(m.group(2))
    if not 1 <= month <= 12:
        return None
    return date(year, month, 1)


def _parse_csv(
    text: str,
    ds_id: str,
    area: str | None,
    title: str,
    cutoff: date,
) -> list[dict]:
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        return []
    if len(header) < 6:
        logger.warning("[%s] dataset %s: unexpected header width", _SOURCE_KEY, ds_id)
        return []

    periods: list[tuple[int, date]] = []
    for idx, label in enumerate(header[5:], start=5):
        obs_date = _period_to_date(label)
        if obs_date is not None and obs_date > cutoff:
            periods.append((idx, obs_date))
    if not periods:
        return []

    src_url = _CSV_URL.format(id=ds_id)
    ts = get_scrape_ts()
    rows: list[dict] = []
    for record in reader:
        if len(record) < 6:
            continue
        item_ru = (record[2] or "").strip()
        item_en = (record[3] or "").strip()
        if not item_ru:
            continue
        for idx, obs_date in periods:
            if idx >= len(record):
                continue
            raw = (record[idx] or "").strip()
            if not raw:
                continue
            try:
                price = float(raw)
            except ValueError:
                continue
            # The publisher writes unobserved months as 0.0, not as a blank.
            if price <= 0:
                continue
            note = f"stat.uz average market price ({title})"
            if item_en:
                note = f"{note}; en={item_en}"
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "monthly",
                "country": _COUNTRY,
                "subnational_area": area,
                "source_key": _SOURCE_KEY,
                "item_name": item_ru,
                "price_local": round(price, 4),
                "currency": _CURRENCY,
                "unit": None,
                "source_url": src_url,
                "notes": note,
                "scrape_ts": ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)
    return rows


def fetch_uz_stat_avg_prices(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    try:
        page = session.get(_INDEX_URL, timeout=60)
        page.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] index page fetch failed: %s", _SOURCE_KEY, exc)
        return None

    datasets = _discover_datasets(page.text)
    if not datasets:
        logger.warning(
            "[%s] no 'средних цен ... рынках' datasets found on index page",
            _SOURCE_KEY,
        )
        return None
    logger.info("[%s] %d market datasets discovered", _SOURCE_KEY, len(datasets))

    all_rows: list[dict] = []
    for ds_id, area, title in datasets:
        url = _CSV_URL.format(id=ds_id)
        try:
            resp = session.get(url, timeout=120)
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] dataset %s fetch failed: %s", _SOURCE_KEY, ds_id, exc)
            continue
        text = resp.content.decode("utf-8-sig", "ignore")
        rows = _parse_csv(text, ds_id, area, title, cutoff)
        logger.info(
            "[%s] dataset %s (%s): %d rows", _SOURCE_KEY, ds_id, area or "national", len(rows)
        )
        all_rows.extend(rows)

    logger.info("[%s] %d rows total (cutoff=%s)", _SOURCE_KEY, len(all_rows), cutoff)
    return pd.DataFrame(all_rows) if all_rows else None
