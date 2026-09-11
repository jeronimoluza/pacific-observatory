"""Sri Lanka DCS (Department of Census & Statistics) — Weekly Retail Prices.

Government weekly retail price series (absolute prices, not an index),
collected across 14 markets in the Colombo district. The dashboard's data
source is a raw JS data file, not a JSON API: re-verified live 2026-08-06,
GET https://www.statistics.gov.lk/DashBoard/Prices/Prices_Data.php -> 200,
1.85MB body containing `var pip=[...]` (122 named products with category)
and `var prices=[...]` (456 weekly rows, one dict per week keyed by product
code, back to 2017). Sample: 'Ash Plantain  1kg' (Low Country Vegetables),
week 'W4.June.2026' price 281.43 LKR.

Missing values are written as the invalid-JSON literal `''` (single-quoted
empty string) rather than `null`, so the raw JS array text is cleaned before
`json.loads`. Week labels are `W<n>.<Month>.<Year>` (month spelled either
abbreviated or in full across the file's history) and are converted to an
approximate date (first day of month + (n-1) weeks) since no exact day is
published.

`_COICOP_MAP` stamps a per-ITEM COICOP-2018 leaf on the emitted row while the
manifest stays `coicop_classification: classifier`. That pairing is deliberate:
`concatenate`'s `_classifier_csv_map` ingests a fetcher's price_observations.csv
ONLY for `classifier` sources, and the per-row code then rides through as
`declared_coicop_codes` and short-circuits the head in `classify`
(`state=narrow_source`, confidence 1.0). Declaring `source_curated` would remove
this file from the corpus entirely.

The map is keyed on the dashboard's own `product` CODE ("Katta_DRIEDFISH_1Kg"),
not on `name`. The names carry double spaces and at least one publisher typo
("Cabbagge Seed  1kg", which the code confirms is cabbage), so the code is the
stabler key and it also states the category the leaf was chosen under.

Judgement calls worth knowing about, all flagged in the enumeration CSV as
medium confidence: betel leaves and arecanuts are masticatories and go to
02.4.0.0 (Narcotics), the COICOP home for betel/areca, not to a food leaf;
"MaldiveFish" is cured dried tuna (01.1.3.2.9) despite sitting in the
publisher's Spices category; Lactogen I/II are infant formula (01.1.9.2.1)
while the other five 400g milk-powder brands are plain powdered milk
(01.1.4.3.2); beetroot and radish have no dedicated leaf and take
01.1.7.4.9. A label in neither `_COICOP_MAP` nor `_NON_COICOP_ITEMS` is logged
and left uncoded for the classifier, never guessed at.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, timedelta

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://www.statistics.gov.lk/DashBoard/Prices/Prices_Data.php"
_COUNTRY = "Sri Lanka"
_CURRENCY = "LKR"
_SOURCE_KEY = "lk_dcs_weekly_retail"
_IDENT = ["source_key", "observation_date", "item_name"]

# DCS dashboard `product` code -> COICOP-2018 leaf
# (src/data/prices/enrich/gold/coicop_leaves.txt).
_COICOP_MAP = {
    "Anamalu_FRUITS_1Kg": "01.1.6.1.2",
    "Anchor_MILK_POWDER_MILK_400g": "01.1.4.3.2",
    "Arecanuts_Average_ARECANUTS_100Nuts": "02.4.0.0",
    "Arecanuts_Medium_ARECANUTS_100Nuts": "02.4.0.0",
    "Arecanuts_Small_ARECANUTS_100Nuts": "02.4.0.0",
    "Ash_Plantain_LCVEG_1kg": "01.1.7.5.7",
    "Ash_Pumpkin_LCVEG_1kg": "01.1.7.2.5",
    "B.Onions_Imported_BIGONIONS_1kg": "01.1.7.4.3",
    "B.Onions_Local_BIGONIONS_1kg": "01.1.7.4.3",
    "Balaya_SEAFISH_LARGE_1Kg": "01.1.3.1.5",
    "Bandakka_LCVEG_1kg": "01.1.7.2.6",
    "Beans_Butter_UPCVEG_1kg": "01.1.7.3.1",
    "Beans_Green_UPCVEG_1kg": "01.1.7.3.2",
    "Beef_MEAT_1Kg": "01.1.2.2.1",
    "BeetRoot_UPCVEG_1kg": "01.1.7.4.9",
    "Betel_Leaves_Average_B_LEAVES_100leaves": "02.4.0.0",
    "Betel_Leaves_Medium_B_LEAVES_100leaves": "02.4.0.0",
    "Betel_Leaves_Small_B_LEAVES_100leaves": "02.4.0.0",
    "Bitter_Guard_LCVEG_1kg": "01.1.7.2.9",
    "Bread_U_BAKERY_450g": "01.1.1.3.1",
    "Brinjal_LCVEG_1kg": "01.1.7.2.3",
    "CabbaggeSeed_UPCVEG_1kg": "01.1.7.1.2",
    "Cap_Chillies_LCVEG_1kg": "01.1.7.2.1",
    "Carrot_UPCVEG_1kg": "01.1.7.4.1",
    "Chicken_Broiler_MEAT_1Kg": "01.1.2.2.4",
    "Chicken_Fresh_MEAT_1Kg": "01.1.2.2.4",
    "Cinnamon_SPICES_1Kg": "01.1.9.4.0",
    "CoconutOil_OILANDFATS_750ml": "01.1.5.1.6",
    "Coconut_Average_COCONUT_Each": "01.1.6.1.8",
    "Coconut_Large_COCONUT_Each": "01.1.6.1.8",
    "Coconut_Medium_COCONUT_Each": "01.1.6.1.8",
    "Coconut_small_COCONUT_Each": "01.1.6.1.8",
    "Corriander_SPICES_1Kg": "01.1.9.4.0",
    "Cowpea_Whole_Average_PULSESANDFLOUR_1Kg": "01.1.7.6.6",
    "Cucumber_LCVEG_1kg": "01.1.7.2.2",
    "CumminSeed_SPICES_1Kg": "01.1.9.4.0",
    "Dried_Chillies_No1._SPICES_1Kg": "01.1.9.4.0",
    "Drumstick_LCVEG_1kg": "01.1.7.2.9",
    "Egg_Average_EGGS_Each": "01.1.4.8.1",
    "Egg_Red_EGGS_Each": "01.1.4.8.1",
    "Egg_White_EGGS_Each": "01.1.4.8.1",
    "Fennel_Seed_SPICES_1Kg": "01.1.9.4.0",
    "Garlic_SPICES_1Kg": "01.1.7.4.2",
    "Gorakka_SPICES_1Kg": "01.1.9.4.0",
    "Gotukola_LEAVES_Bunch": "01.1.7.1.9",
    "Green_Chillies_LCVEG_1kg": "01.1.7.2.1",
    "Green_Gram_Average_PULSESANDFLOUR_1Kg": "01.1.7.6.9",
    "Highland_MILK_POWDER_MILK_400g": "01.1.4.3.2",
    "Hurulla_SEAFISH_SMALL_1Kg": "01.1.3.1.6",
    "Kadalai_Average_PULSESANDFLOUR_1Kg": "01.1.7.6.3",
    "Kankun_LEAVES_Bunch": "01.1.7.1.9",
    "Kathurumurunga_LEAVES_Bunch": "01.1.7.1.9",
    "Katta_DRIEDFISH_1Kg": "01.1.3.2.9",
    "Kelewella_SEAFISH_LARGE_1Kg": "01.1.3.1.5",
    "KnolKhol_UPCVEG_1kg": "01.1.7.1.9",
    "Kohila_Leaves_LEAVES_Bunch": "01.1.7.1.9",
    "Kohila_Yams_LCVEG_1kg": "01.1.7.5.9",
    "Kolikuttu_FRUITS_1Kg": "01.1.6.1.2",
    "Lactogen_II_MILK_POWDER_MILK_400g": "01.1.9.2.1",
    "Lactogen_I_MILK_POWDER_MILK_400g": "01.1.9.2.1",
    "Lakspray_MILK_POWDER_MILK_400g": "01.1.4.3.2",
    "Leeks_UPCVEG_1kg": "01.1.7.4.4",
    "Limes_LCVEG_1kg": "01.1.6.2.2",
    "Linna_SEAFISH_SMALL_1Kg": "01.1.3.1.6",
    "LongBeans_LCVEG_1kg": "01.1.7.3.2",
    "MaldiveFish_U_SPICES_1Kg": "01.1.3.2.9",
    "Maliban_MILK_POWDER_MILK_400g": "01.1.4.3.2",
    "Mathe_Seed_SPICES_1Kg": "01.1.9.4.0",
    "Mora_SEAFISH_LARGE_1Kg": "01.1.3.1.9",
    "Mukunuwenna_LEAVES_Bunch": "01.1.7.1.9",
    "Mullet_SEAFISH_LARGE_1Kg": "01.1.3.1.9",
    "Mustard_SPICES_1Kg": "01.1.9.4.0",
    "Mutton_MEAT_1Kg": "01.1.2.2.3",
    "Mysore_Dhall_Average_PULSESANDFLOUR_1Kg": "01.1.7.6.4",
    "Mysore_Dhall_No1._Large_PULSESANDFLOUR_1Kg": "01.1.7.6.4",
    "Mysore_Dhall_No2.Medium_PULSESANDFLOUR_1Kg": "01.1.7.6.4",
    "Mysore_Dhall_No3.Small_PULSESANDFLOUR_1Kg": "01.1.7.6.4",
    "Nadu_Red_RICE_1Kg": "01.1.1.1.2",
    "Nadu_White_Imported_RICE_1Kg": "01.1.1.1.2",
    "Nadu_White_RICE_1Kg": "01.1.1.1.2",
    "Nivithi_LEAVES_500g": "01.1.7.1.5",
    "Papaw_FRUITS_1Kg": "01.1.6.1.6",
    "Parati_SEAFISH_SMALL_1Kg": "01.1.3.1.9",
    "Paraw_SEAFISH_LARGE_1Kg": "01.1.3.1.6",
    "Pelwatta_MILK_POWDER_MILK_400g": "01.1.4.3.2",
    "Pepper_Powder_SPICES_1Kg": "01.1.9.4.0",
    "Pineapple_FRUITS_1Kg": "01.1.6.1.7",
    "Ponni_Samba_Imported_RICE_1Kg": "01.1.1.1.2",
    "Pork_MEAT_1Kg": "01.1.2.2.2",
    "Potatoes_Imported_POTATOES_1Kg": "01.1.7.5.1",
    "Potatoes_Local_POTATOES_1Kg": "01.1.7.5.1",
    "Prawns_SEAFISH_SMALL_1Kg": "01.1.3.4.1",
    "Raddish_UPCVEG_1kg": "01.1.7.4.9",
    "Raw_Red_Average_RICE_1Kg": "01.1.1.1.2",
    "Raw_Red_Imported_RICE_1Kg": "01.1.1.1.2",
    "Raw_Red_No1._RICE_1Kg": "01.1.1.1.2",
    "Raw_Red_No2._RICE_1Kg": "01.1.1.1.2",
    "Raw_White_Average_RICE_1Kg": "01.1.1.1.2",
    "Raw_White_Imported_RICE_1Kg": "01.1.1.1.2",
    "Raw_White_Local_RICE_1Kg": "01.1.1.1.2",
    "Red_Onions_Average_REDONIONS_1Kg": "01.1.7.4.3",
    "Red_Pumpkin_LCVEG_1kg": "01.1.7.2.5",
    "Salaya_Average_DRIEDFISH_1Kg": "01.1.3.2.9",
    "Salaya_SEAFISH_SMALL_1Kg": "01.1.3.1.6",
    "Salt_U_SPICES_1KgPkt": "01.1.9.3.1",
    "Samba_Average_RICE_1Kg": "01.1.1.1.2",
    "Samba_No1._RICE_1Kg": "01.1.1.1.2",
    "Samba_No2._RICE_1Kg": "01.1.1.1.2",
    "Sarana_LEAVES_Bunch": "01.1.7.1.9",
    "SmallMullet_SEAFISH_SMALL_1Kg": "01.1.3.1.9",
    "Snake_Gourd_LCVEG_1kg": "01.1.7.2.9",
    "Sour_Plantain_FRUITS_1Kg": "01.1.6.1.2",
    "Spratts_DRIEDFISH_1Kg": "01.1.3.2.9",
    "Sugar_SUGER_1Kg": "01.1.8.1.1",
    "Tamarind_SPICES_1Kg": "01.1.9.4.0",
    "Thalapath_SEAFISH_LARGE_1Kg": "01.1.3.1.6",
    "Thampala_LEAVES_Bunch": "01.1.7.1.9",
    "TinFish_U_CANNEDFISH_425g": "01.1.3.3.9",
    "Tomatoe_No1._UPCVEG_1kg": "01.1.7.2.4",
    "Turmeric_Powder_SPICES_1Kg": "01.1.9.4.0",
    "Vetakolu_LCVEG_1kg": "01.1.7.2.9",
    "WheatFlour_PULSESANDFLOUR_1Kg": "01.1.1.2.1",
}

# Every item this dashboard publishes is food, drink or a masticatory, so there
# is nothing to exclude today. Kept as an explicit empty collection so a future
# non-food addition has an obvious home and does not read as an oversight.
_NON_COICOP_ITEMS: frozenset[str] = frozenset()

_PIP_RE = re.compile(r"var pip\s*=\s*(\[.*?\]);", re.S)
_PRICES_RE = re.compile(r"var prices\s*=\s*(\[.*?\]);", re.S)
_WEEK_RE = re.compile(r"W(\d+)\.([A-Za-z]+)\.(\d{4})")

_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def _parse_week(label: str) -> date | None:
    m = _WEEK_RE.match(label.strip())
    if not m:
        return None
    week_no, month_txt, year_txt = m.groups()
    month = _MONTHS.get(month_txt.strip().lower())
    if not month:
        return None
    try:
        base = date(int(year_txt), month, 1)
    except ValueError:
        return None
    return base + timedelta(weeks=int(week_no) - 1)


def _load_arrays(text: str) -> tuple[list[dict], list[dict]] | None:
    m_pip = _PIP_RE.search(text)
    m_prices = _PRICES_RE.search(text)
    if not m_pip or not m_prices:
        return None
    try:
        pip = json.loads(m_pip.group(1))
    except ValueError:
        logger.warning("[%s] pip array not valid JSON", _SOURCE_KEY)
        return None
    prices_txt = re.sub(r":\s*''", ":null", m_prices.group(1))
    try:
        prices = json.loads(prices_txt)
    except ValueError:
        logger.warning("[%s] prices array not valid JSON after cleanup", _SOURCE_KEY)
        return None
    return pip, prices


def _rows(pip: list[dict], prices: list[dict], cutoff: date) -> list[dict]:
    meta = {
        p["product"]: (p.get("name", p["product"]).strip(), p.get("category"))
        for p in pip
        if p.get("product")
    }
    ts = get_scrape_ts()
    out: list[dict] = []
    unmapped: set[str] = set()
    for week in prices:
        label = week.get("Date")
        obs_date = _parse_week(label) if label else None
        if obs_date is None or obs_date <= cutoff:
            continue
        for code, value in week.items():
            if code == "Date" or value is None:
                continue
            try:
                price = float(value)
            except (TypeError, ValueError):
                continue
            if not 0 < price < 1_000_000:
                continue
            name, category = meta.get(code, (code, None))
            coicop = _COICOP_MAP.get(code)
            if coicop is None and code not in _NON_COICOP_ITEMS:
                unmapped.add(code)
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "weekly",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": coicop,
                "item_name": name,
                "price_local": round(price, 2),
                "currency": _CURRENCY,
                "unit": None,
                "source_url": _URL,
                "notes": f"category={category}" if category else "",
                "scrape_ts": ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            out.append(row)
    if unmapped:
        logger.warning(
            "[%s] %d product code(s) in neither _COICOP_MAP nor "
            "_NON_COICOP_ITEMS, left uncoded for the classifier: %s",
            _SOURCE_KEY,
            len(unmapped),
            sorted(unmapped),
        )
    return out


def fetch_lk_dcs_weekly_retail(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    try:
        resp = session.get(_URL, timeout=90)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] fetch failed: %s", _SOURCE_KEY, exc)
        return None
    resp.encoding = resp.apparent_encoding or "utf-8"
    arrays = _load_arrays(resp.text)
    if not arrays:
        return None
    pip, prices = arrays
    rows = _rows(pip, prices, cutoff)
    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
