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

`_COICOP_MAP` stamps a per-ITEM COICOP-2018 leaf on the emitted row while the
manifest stays `coicop_classification: classifier`. That pairing is deliberate:
`concatenate`'s `_classifier_csv_map` ingests a fetcher's price_observations.csv
ONLY for `classifier` sources, and the per-row code then rides through as
`declared_coicop_codes` and short-circuits the head in `classify`
(`state=narrow_source`, confidence 1.0). Declaring `source_curated` instead
would remove this file from the corpus altogether.

MEASURED CAVEAT, 2026-09-11: a COICOP code is NOT this source's binding
constraint on the published grid. Of its 322 rows inside the dashboard's 90-day
window, only 28 were `qa_status: trusted` -- 98 failed `qa_quantity`
(`review_missing_qty`) and 196 failed the thin-cell check (`review_uv_thin`).
The quantity failures are the `unit: None` decision above meeting bare Russian
commodity nouns that carry no parseable quantity; they will keep failing after
this map lands. Itemising `unit` is the fix for that, and it is a separate job.

The animal-feed tail (Отруби/bran, Шрот/meal, Шелуха/husk, Комбикорм/compound
feed) is listed in `_NON_COICOP_ITEMS`: it is livestock input, not household
consumption, so no division-01/02 leaf applies. Those rows keep a null
`coicop_code` and fall through to the classifier rather than being dropped --
under `classifier` a null is legitimate, and dropping them would destroy
observations rather than merely leave them unlabelled.
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

# stat.uz Klassifikator_ru label -> COICOP-2018 leaf
# (src/data/prices/enrich/gold/coicop_leaves.txt).
_COICOP_MAP = {
    "Арбуз": "01.1.6.5.4",
    "Баклажаны": "01.1.7.2.3",
    "Баранина": "01.1.2.2.3",
    "Виноград": "01.1.6.5.1",
    "Говядина": "01.1.2.2.1",
    "Горох": "01.1.7.6.5",
    "Груши": "01.1.6.3.2",
    "Дыня": "01.1.6.5.3",
    "Капуста": "01.1.7.1.2",
    "Картофель": "01.1.7.5.1",
    "Кишмиш": "01.1.6.7.1",
    "Крупа манная": "01.1.1.9.0",
    "Кукуруза": "01.1.1.1.6",
    "Лимоны": "01.1.6.2.2",
    "Лук репчатый": "01.1.7.4.3",
    "Масло подсолнечное (1 литр)": "01.1.5.1.1",
    "Масло сливочное": "01.1.5.2.1",
    "Масло хлопковое (1 литр)": "01.1.5.1.9",
    "Маш": "01.1.7.6.9",
    "Молоко свежее (1 литр)": "01.1.4.1.1",
    "Морковь": "01.1.7.4.1",
    "Мука пшеничная высшего сорта": "01.1.1.2.1",
    "Мука пшеничная первого сорта": "01.1.1.2.1",
    "Мясо птицы": "01.1.2.2.4",
    "Огурцы": "01.1.7.2.2",
    "Перец болгарский": "01.1.7.2.1",
    "Помидоры": "01.1.7.2.4",
    "Пшеница": "01.1.1.1.1",
    "Рис": "01.1.1.1.2",
    "Рыба всякая": "01.1.3.1.9",
    "Сахар песок": "01.1.8.1.1",
    "Тыква": "01.1.7.2.5",
    "Фасоль": "01.1.7.6.1",
    "Хлеб пшеничный из муки 1-го сорта": "01.1.1.3.1",
    "Чеснок": "01.1.7.4.2",
    "Яблоки": "01.1.6.3.1",
    "Яйца (10 штук)": "01.1.4.8.1",
    "Ячмень": "01.1.1.1.4",
}

# Livestock-feed rows the same dehqan-market tables carry. Not household
# food; no division-01/02 leaf applies, so they stay uncoded.
_NON_COICOP_ITEMS = frozenset(
    {
        "Комбикорм",
        "Отруби",
        "Шелуха",
        "Шрот",
    }
)

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

# Labels seen in neither collection above, accumulated across datasets and
# logged once at the end of a run.
_UNMAPPED: set[str] = set()


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
            coicop = _COICOP_MAP.get(item_ru)
            if coicop is None and item_ru not in _NON_COICOP_ITEMS:
                _UNMAPPED.add(item_ru)
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "monthly",
                "country": _COUNTRY,
                "subnational_area": area,
                "source_key": _SOURCE_KEY,
                "coicop_code": coicop,
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
    _UNMAPPED.clear()
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

    if _UNMAPPED:
        logger.warning(
            "[%s] %d item label(s) in neither _COICOP_MAP nor _NON_COICOP_ITEMS, "
            "left uncoded for the classifier: %s",
            _SOURCE_KEY,
            len(_UNMAPPED),
            sorted(_UNMAPPED),
        )
    logger.info("[%s] %d rows total (cutoff=%s)", _SOURCE_KEY, len(all_rows), cutoff)
    return pd.DataFrame(all_rows) if all_rows else None
