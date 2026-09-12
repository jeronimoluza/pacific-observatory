"""Economic Association Foundation (مؤسسة الرابطة الاقتصادية), Aden, Yemen --
weekly consumer price monitoring of essential food commodities.

`eaf-ye.com/commodities.php` is a single page holding the whole archive as a
stack of HTML tables, one per reporting period, for Aden governorate. Prices
are in Yemeni rial. The page's own footer states the method: "يتم الرصد كل يوم
سبت من كل أسبوع" -- collection every Saturday.

DATING -- WHY THIS SOURCE WAS PREVIOUSLY REJECTED, AND WHY IT IS USABLE
----------------------------------------------------------------------
A previous pass rejected this page as undatable: the tables themselves carry
only ordinal week columns ("الاسبوع الأول".."الاسبوع الخامس") and no calendar
date anywhere inside the table markup, and a search for date-shaped strings
over the whole page returns three (2023/1/14, /21, /28).

The dates are in the HEADING that immediately PRECEDES each table, walking
backwards in document order:

    اسعار السلع الاساسية من الاسواق لشهر ديسمبر 2023
    اسعار السلع الاساسية من الاسواق للربع الرابع من عام 2022م
    اسعار السلع الاساسية من الاسواق لشهر ديسمبر عام ٢٠٢١م

so every one of the 17 tables resolves to a month or a quarter. The year is
occasionally written in Arabic-Indic digits (٢٠٢١) and is transliterated.
A table whose heading yields no period is SKIPPED -- an undated price row is
pollution, not coverage.

TWO TABLE SHAPES
----------------
  * Monthly (2023, and Dec 2021): one column per week of the month plus a unit
    column. Source order is RTL, so a data row reads
    [week-5, week-4, week-3, week-2, week-1, unit, name, row-number] and the
    parser takes the name from cells[-2] and the unit from cells[-3] -- never a
    fixed index, because a month with four weeks simply drops a column.
    The weekly readings carry no calendar dates of their own, so the MEAN of
    the weeks present is emitted once, as `monthly_avg`. Inventing a date for
    "week 3" would be making one up.
  * Period-average (the four 2022 quarters and Dec 2021): [row-number, name,
    price in YER, price in USD]. Only the YER column is emitted; the USD column
    is the association's own conversion at its own rate and is not an
    independent observation.

The two shapes are told apart per ROW rather than per table, by where the
one- or two-digit row number sits.

UNITS ARE PER-ROW AND THEY CHANGE
---------------------------------
The pack size is published, not implied, and it moved between eras: cooking oil
is an 8-litre tin in the 2023 monthly tables and a 4-litre tin in the 2022
quarterly ones (18,000 YER against 19,043 YER -- reading both as the same unit
would invent a halving). So the unit is read from the unit column in the
monthly tables and out of the item label in the average tables, and is emitted
per row. The header calls the unit column "وحدة القياس (كيلو)", so a bare
number there is kilograms unless the label says otherwise (grams for the
macaroni row, litres for oil, a carton for tomato paste).

COICOP
------
`_COICOP_RULES` matches the normalised Arabic label against an ordered list of
substrings, because the same commodity is labelled differently in the two table
shapes ("كيس القمح" against "كيس القمح الامريكي 50كيلو"). A label matching
nothing is logged and DROPPED.

`coicop_classification: classifier` with a per-row `coicop_code` is deliberate
and matches zm_mfl_market_bulletin: concatenate._build_classifier_csv_map
ingests a fetcher CSV only for `classifier` sources, so `source_curated` would
delete this source's rows from the build.

Emits PriceObservation rows.
"""

from __future__ import annotations

import logging
import re
import statistics
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://eaf-ye.com/commodities.php"
_COUNTRY = "Yemen, Rep."
_CURRENCY = "YER"
_SOURCE_KEY = "ye_eaf_consumer_prices"
_AREA = "Aden"

_IDENT = ["source_key", "observation_date", "subnational_area", "item_name"]

_AR_MONTHS = {
    "يناير": 1, "فبراير": 2, "مارس": 3, "ابريل": 4, "مايو": 5, "يونيو": 6,
    "يوليو": 7, "اغسطس": 8, "سبتمبر": 9, "اكتوبر": 10, "نوفمبر": 11,
    "ديسمبر": 12,
}
_AR_QUARTERS = {"الاول": 1, "الثاني": 2, "الثالث": 3, "الرابع": 4}

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_DIACRITICS = re.compile("[ً-ْـ]")

_MONTH_RE = re.compile(r"لشهر\s+([؀-ۿ]+)(?:\s+عام)?\s*(\d{4})")
_QUARTER_RE = re.compile(r"للربع\s+([؀-ۿ]+)\s+من\s+عام\s*(\d{4})")

# Ordered: the first substring found in the normalised label wins, so the more
# specific label must come first ("الحليب المجفف" before any bare "حليب").
_COICOP_RULES: list[tuple[str, str, str]] = [
    ("كيس القمح", "Wheat, sack", "01.1.1.1.1"),
    ("دقيق السنابل", "Wheat flour, Sanabel white", "01.1.1.2.1"),
    ("ارز الفخامه", "Rice, Al-Fakhama", "01.1.1.1.2"),
    ("مكرونه الماىده", "Macaroni, Al-Maida", "01.1.1.5.0"),
    ("سكر", "Sugar, white", "01.1.8.1.1"),
    ("زيت الطبخ", "Cooking oil", "01.1.5.1.9"),
    ("حليب الاطفال", "Infant formula, Bebelac no. 3", "01.1.9.2.1"),
    ("الحليب المجفف", "Powdered milk, Dano full cream", "01.1.4.3.2"),
    ("شاي الكبوس", "Tea, Al-Kabous", "01.2.3.0.2"),
    ("الفاصوليا الحمراء", "Red kidney beans, dried", "01.1.7.6.1"),
    ("الفاصوليا البيضاء", "White beans, dried", "01.1.7.6.1"),
    ("العدس الاصفر", "Yellow lentils, dried", "01.1.7.6.4"),
    ("معجون الطماطم", "Tomato paste, Al-Mudhish", "01.1.7.9.2"),
    ("التفاح", "Apples", "01.1.6.3.1"),
    ("البرتقال", "Oranges", "01.1.6.2.3"),
    ("الموز", "Bananas", "01.1.6.1.2"),
    ("التمور", "Dates", "01.1.6.1.3"),
    ("البطاطس", "Potatoes", "01.1.7.5.1"),
    ("البصل الجاف", "Onions, dry", "01.1.7.4.3"),
    ("الباذنجان", "Aubergine", "01.1.7.2.3"),
    ("الطماطم", "Tomatoes", "01.1.7.2.4"),
    ("الباميا", "Okra", "01.1.7.2.6"),
    ("لحم الغنم", "Mutton", "01.1.2.2.3"),
    ("الدجاج الحي", "Chicken, live", "01.1.2.1.4"),
    ("الدجاج المجمد", "Chicken, frozen", "01.1.2.2.4"),
    ("طبق البيض", "Eggs, tray", "01.1.4.8.1"),
    ("الثمد", "Thamad fish, fresh", "01.1.3.1.9"),
    ("الديرك", "Deirak fish, fresh", "01.1.3.1.9"),
    ("السخله", "Sakhla fish, fresh", "01.1.3.1.9"),
]


def _norm_ar(s: object) -> str:
    """Strip tatweel and diacritics, fold the alef/ya/ta-marbuta variants and
    collapse whitespace. The same commodity is spelled inconsistently across
    eras (أرز / ارز, المائدة / الماىده), so the rules key on the folded form."""
    t = str(s or "").replace("\xa0", " ").translate(_AR_DIGITS)
    t = _DIACRITICS.sub("", t)
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ة", "ه"), ("ى", "ي"), ("ئ", "ى")):
        t = t.replace(a, b)
    return re.sub(r"\s+", " ", t).strip()


def _period(heading: str) -> tuple[date, str] | None:
    text = _norm_ar(heading)
    m = _MONTH_RE.search(text)
    if m:
        month = _AR_MONTHS.get(_norm_ar(m.group(1)))
        if month:
            return date(int(m.group(2)), month, 1), "monthly_avg"
    m = _QUARTER_RE.search(text)
    if m:
        quarter = _AR_QUARTERS.get(_norm_ar(m.group(1)))
        if quarter:
            return date(int(m.group(2)), 3 * quarter - 2, 1), "quarterly_avg"
    return None


def _heading_for(table) -> str | None:
    """The nearest preceding text node naming a month or a quarter."""
    seen = 0
    for node in table.find_all_previous(string=True):
        text = _norm_ar(node)
        if not text:
            continue
        seen += 1
        if seen > 40:
            break
        if _MONTH_RE.search(text) or _QUARTER_RE.search(text):
            return text
    return None


def _value(cell: str) -> float | None:
    raw = _norm_ar(cell).replace(",", "").replace(" ", "")
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def _is_index(cell: str) -> bool:
    raw = _norm_ar(cell)
    return bool(re.fullmatch(r"\d{1,2}", raw))


def _has_letters(cell: str) -> bool:
    return bool(re.search(r"[؀-ۿA-Za-z]", _norm_ar(cell)))


def _unit_from_cell(unit_cell: str, label: str) -> str:
    """The unit column is headed "وحدة القياس (كيلو)", so a bare number there
    is kilograms -- unless the item label overrides it, which it does for the
    macaroni (grams) and the tomato-paste carton."""
    raw = _norm_ar(unit_cell)
    lab = _norm_ar(label)
    if "كرتون" in raw or "كرتون" in lab:
        return "carton"
    amount = re.search(r"\d+(?:\.\d+)?", raw)
    if "لتر" in raw:
        return f"{amount.group(0)} L" if amount else "L"
    if not amount:
        return raw or "each"
    # "جم" must be a standalone token: it is also a substring of "المجمد"
    # (frozen), which silently turned frozen chicken into a 1 g price.
    if re.search(r"(?:^|[\s\d(])(?:جرام|جم)(?:[\s)]|$)", lab):
        return f"{amount.group(0)} g"
    return f"{amount.group(0)} kg"


def _unit_from_label(label: str) -> str:
    """The period-average tables carry no unit column; the pack size is written
    into the label ("زيت الطبخ بيت الكرم 4 لتر", "التفاح (1) كجم")."""
    lab = _norm_ar(label)
    if "كرتون" in lab:
        return "carton"
    m = re.search(r"(\d+(?:\.\d+)?)\s*(كيلو|كجم|كغم|لتر|جرام|جم)", lab)
    if not m:
        m2 = re.search(r"\((\d+(?:\.\d+)?)\)\s*(كيلو|كجم|كغم|لتر|جرام|جم)", lab)
        m = m2 or m
    if not m:
        return "each"
    amount, unit = m.group(1), m.group(2)
    if unit == "لتر":
        return f"{amount} L"
    if unit in {"جرام", "جم"}:
        return f"{amount} g"
    return f"{amount} kg"


def _month_price(values: list[float]) -> float | None:
    """The month's average from a weekly row.

    Some months are published as bare weekly columns and some append the
    publisher's own "متوسط أسعار شهر <this month>" and "<last month>" columns
    after them. Which layout a table uses is not declared, so it is TESTED: if
    the mean of everything but the last two values reproduces the
    second-to-last value, those trailing columns are the two monthly averages
    and the publisher's own figure for this month is used. Otherwise every
    value is a week and they are averaged. Without this check the previous
    month's average would be folded into this month's mean."""
    if not values:
        return None
    if len(values) >= 3:
        weeks, this_month = values[:-2], values[-2]
        mean = statistics.fmean(weeks)
        if abs(mean - this_month) <= max(1.0, 0.02 * abs(this_month)):
            return this_month
    return statistics.fmean(values)


def _lookup(label: str) -> tuple[str, str] | None:
    lab = _norm_ar(label)
    for needle, item, coicop in _COICOP_RULES:
        if needle in lab:
            return item, coicop
    return None


def fetch_ye_eaf_consumer_prices(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    session.verify = False
    resp = session.get(_URL, timeout=180)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content.decode("utf-8", "replace"), "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()

    rows: list[dict] = []
    unknown: set[str] = set()
    undated = 0
    scrape_ts = get_scrape_ts()

    for table in soup.find_all("table"):
        heading = _heading_for(table)
        period = _period(heading) if heading else None
        if period is None:
            undated += 1
            continue
        obs, period_kind = period
        if obs <= cutoff:
            continue
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            cells = [c for c in cells if c and c.strip()]
            if len(cells) < 3:
                continue
            if _is_index(cells[-1]) and _has_letters(cells[-2]):
                # RTL weekly shape: [...weeks..., unit, name, row-number]
                label, unit_cell = cells[-2], cells[-3]
                values = [v for v in (_value(c) for c in cells[:-3]) if v is not None]
                unit = _unit_from_cell(unit_cell, label)
                price = _month_price(values)
            elif _is_index(cells[0]) and _has_letters(cells[1]):
                label = cells[1]
                rest = cells[2:]
                if len(rest) <= 2:
                    # LTR period-average shape: [row-number, name, YER, USD].
                    # Only the YER column is emitted.
                    price = _value(rest[0]) if rest else None
                    unit = _unit_from_label(label)
                else:
                    # LTR weekly shape: [row-number, name, unit, ...weeks,
                    # this-month average, last-month average].
                    unit = _unit_from_cell(rest[0], label)
                    values = [v for v in (_value(c) for c in rest[1:]) if v is not None]
                    price = _month_price(values)
            else:
                continue
            if price is None:
                continue
            spec = _lookup(label)
            if spec is None:
                unknown.add(_norm_ar(label))
                continue
            item, coicop = spec
            row = {
                "observation_date": obs.isoformat(),
                "period_kind": period_kind,
                "country": _COUNTRY,
                "subnational_area": _AREA,
                "source_key": _SOURCE_KEY,
                "coicop_code": coicop,
                "item_name": item,
                "price_local": round(price, 2),
                "currency": _CURRENCY,
                "unit": unit,
                "source_url": _URL,
                "notes": "consumer price monitoring, Aden governorate"
                + ("; mean of the weekly readings published for the month"
                   if period_kind == "monthly_avg" else ""),
                "scrape_ts": scrape_ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    if unknown:
        logger.warning(
            "%s: %d unmapped commodity label(s), not emitted: %s",
            _SOURCE_KEY, len(unknown), "; ".join(sorted(unknown)),
        )
    if undated:
        logger.warning(
            "%s: %d table(s) skipped -- no month or quarter in the preceding heading",
            _SOURCE_KEY, undated,
        )
    if not rows:
        return None
    df = pd.DataFrame(rows)
    before = len(df)
    df = df.drop_duplicates(subset="observation_hash", keep="first")
    if len(df) != before:
        logger.info("%s: dropped %d duplicate row(s)", _SOURCE_KEY, before - len(df))
    return df
