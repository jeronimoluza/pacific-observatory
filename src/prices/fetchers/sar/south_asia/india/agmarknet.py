"""AGMARKNET — India daily wholesale mandi (market) prices, via data.gov.in.

agmarknet.gov.in itself 403s from outside India (confirmed via curl and a real
Chromium instance — a network-level geofence, not a bot check) and its e-NAM
mirror at enam.gov.in/dashboard/agmarknet returns HTTP 500 on every dynamic
endpoint (Agm_ctrl/*, Ajax_ctrl/*, Liveprice_ctrl/*), reproduced with a real
Playwright browser session, so the backend is down site-wide rather than
bot-gated. The same dataset is republished on the Open Government Data (OGD)
platform (data.gov.in) as "Variety-wise Daily Market Prices Data of Commodity"
and is reachable: the resource's public preview page
(https://www.data.gov.in/resource/variety-wise-daily-market-prices-data-commodity)
embeds a working sample `api-key` for its own resource id, which this fetcher
uses against the documented api.data.gov.in REST endpoint.

Re-verified live 2026-08-07: resource id 35985678-0d79-46b4-9ed6-6f13308a1d24,
81M+ total records, `updated_date` on the resource metadata is same-day.
Sorting/filtering by Arrival_Date confirms rows for the current day are
already posted (e.g. 4 rows for 07/08/2026 at time of probe, 17,471 rows for
06/08/2026 — a full day's catalog). Sample: Commodity 'Ginger(Green)',
Variety 'Green Ginger', Market 'Siliguri APMC', District Darjeeling, State
West Bengal, Modal_Price 11500 (Min 11000 / Max 12000). Modal_Price is
Rs./Quintal — data.gov.in's own field description for this resource states
"Modal Price (Rs./Quintal)" and this holds across every commodity in the
dataset, not just a sampled subset.

This is a whole-catalog walker, not a targeted extractor: every commodity /
variety / market / state the API returns is emitted, unfiltered. The API
supports an exact-match `filters[Arrival_Date]=DD/MM/YYYY` (India date
order) that returns a full day's national catalog in one call when `limit`
is set above the day's row count (a single day has run comfortably to
~17.5K rows with `limit=20000`, no server-side cap observed at that size);
a defensive offset loop still guards against a day that exceeds `_LIMIT`.
Walks backward from today, stopping at `cutoff` or after `_MAX_DAYS_BACK`
days, mirroring the bounded-backward-walk pattern used by the Nepal
Kalimati market fetcher — a full historical backfill of this dataset is
several orders of magnitude larger than one onboarding run should pull.

COICOP is deferred to the downstream classifier — item_name is the WFP-style
free-text commodity (+ variety when the variety differs from the commodity
name), and the catalog spans essentially the entire food division 01 plus
several non-food agricultural commodities (cotton, jute, spices used
industrially, flowers).
"""

from __future__ import annotations

import logging
import time
from datetime import date, timedelta

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_RESOURCE_ID = "35985678-0d79-46b4-9ed6-6f13308a1d24"
_API_KEY = "579b464db66ec23bdd000001cdc3b564546246a772a26393094f5645"
_API_URL = f"https://api.data.gov.in/resource/{_RESOURCE_ID}"
_RESOURCE_PAGE = (
    "https://www.data.gov.in/resource/variety-wise-daily-market-prices-data-commodity"
)
_COUNTRY = "India"
_CURRENCY = "INR"
_UNIT = "quintal (100 kg)"
_SOURCE_KEY = "in_agmarknet"
_IDENT = ["source_key", "observation_date", "item_name", "market", "grade"]
_MAX_DAYS_BACK = 7
_LIMIT = 20000
_EMPTY_VARIETY = {"", "other", "-", "na", "n/a"}

# Hand-curated COICOP 2018 leaf per AGMARKNET `Commodity`, built by enumerating
# all 304 distinct commodities (1,213 commodity+variety item_names) in the
# collected catalogue (2026-09-11). Keyed on the raw API Commodity field, not on
# item_name: the Variety suffix is a cultivar or grade and never changes the
# leaf. Emitted as the row's `coicop_code`, which `concatenate.py` forwards as
# `declared_coicop_codes` for classify.py's narrow_source short-circuit; the
# manifest stays `coicop_classification: classifier` so the rows keep reaching
# the corpus, and an unmapped commodity falls through to the model.
#
# Audited against the production classifier: 92.4% row agreement, but wrong on
# 37 names / 20,441 rows -- most notably `Drumstick` (the moringa pod) -> Meat
# of poultry on 6,701 rows, `Mustard` (mandi seed) -> table condiment, `Peas
# Wet` (fresh) -> canned vegetables, and the vernacular pulses (arhar/tur,
# chana, masur) losing species identity to the residual "other pulses" leaf.
_COICOP_MAP: dict[str, str] = {
    'Ajwan': '01.1.9.4.0',
    'Alasande Gram': '01.1.7.6.6',
    'Almond(Badam)': '01.1.6.8.1',
    'Alsandikai': '01.1.7.3.2',
    'Amla(Nelli Kai)': '01.1.6.5.9',
    'Amranthas Red': '01.1.7.1.9',
    'Apple': '01.1.6.3.1',
    'Apricot(Jardalu/Khumani)': '01.1.6.3.3',
    'Arecanut(Betelnut/Supari)': '02.4.0.0',
    'Asalia': '01.1.9.4.0',
    'Ashgourd': '01.1.7.2.5',
    'Asparagus': '01.1.7.1.1',
    'Avare Dal': '01.1.7.6.1',
    'Bael': '01.1.6.1.9',
    'Bajra(Pearl Millet/Cumbu)': '01.1.1.1.5',
    'Balekai': '01.1.7.5.7',
    'Banana': '01.1.6.1.2',
    'Banana - Green': '01.1.7.5.7',
    'Barley(Jau)': '01.1.1.1.4',
    'Bay leaf(Tejpatta)': '01.1.9.4.0',
    'Beans': '01.1.7.3.1',
    'Beaten Rice': '01.1.1.9.0',
    'Beetroot': '01.1.7.4.9',
    'Bengal Gram Dal(Chana Dal)': '01.1.7.6.3',
    'Bengal Gram(Gram)(Whole)': '01.1.7.6.3',
    'Ber(Zizyphus/Borehannu)': '01.1.6.5.9',
    'Betal Leaves': '02.4.0.0',
    'Betelnuts': '02.4.0.0',
    'Bhindi(Ladies Finger)': '01.1.7.2.6',
    'Big Gram': '01.1.7.6.3',
    'Bitter gourd': '01.1.7.2.9',
    'Black Gram Dal(Urd Dal)': '01.1.7.6.9',
    'Black Gram(Urd Beans)(Whole)': '01.1.7.6.9',
    'Black pepper': '01.1.9.4.0',
    'Bottle gourd': '01.1.7.2.5',
    'Brinjal': '01.1.7.2.3',
    'Broken Rice': '01.1.1.1.2',
    'Bull': '01.1.2.1.1',
    'Bunch Beans': '01.1.7.3.2',
    'Cabbage': '01.1.7.1.2',
    'Calf': '01.1.2.1.1',
    'Capsicum': '01.1.7.2.1',
    'Cardamom': '01.1.9.4.0',
    'Carrot': '01.1.7.4.1',
    'Cashewnuts': '01.1.6.8.2',
    'Cauliflower': '01.1.7.1.3',
    'Chapparad Avare': '01.1.7.3.2',
    'Chennangi Dal': '01.1.7.6.9',
    'Cherry': '01.1.6.3.4',
    'Chikoos(Sapota)': '01.1.6.1.9',
    'Chili Red': '01.1.9.4.0',
    'Chilly Capsicum': '01.1.7.2.1',
    'Chow Chow': '01.1.7.2.9',
    'Cinamon(Dalchini)': '01.1.9.4.0',
    'Cloves': '01.1.9.4.0',
    'Cluster beans': '01.1.7.3.2',
    'Cock': '01.1.2.1.4',
    'Cocoa': '01.1.8.5.2',
    'Coconut': '01.1.6.1.8',
    'Coconut Oil': '01.1.5.1.6',
    'Coffee': '01.2.2.0.1',
    'Colacasia': '01.1.7.5.5',
    'Copra': '01.1.6.7.9',
    'Coriander(Leaves)': '01.1.9.4.0',
    'Corriander seed': '01.1.9.4.0',
    'Cow': '01.1.2.1.1',
    'Cowpea(Lobia/Karamani)': '01.1.7.6.6',
    'Cowpea(Veg)': '01.1.7.3.2',
    'Cucumbar(Kheera)': '01.1.7.2.2',
    'Cummin Seed(Jeera)': '01.1.9.4.0',
    'Custard Apple(Sharifa)': '01.1.6.1.9',
    'Drumstick': '01.1.7.2.9',
    'Dry Chillies': '01.1.9.4.0',
    'Dry Grapes': '01.1.6.7.1',
    'Duck': '01.1.2.1.4',
    'Duster Beans': '01.1.7.3.2',
    'Egg': '01.1.4.8.1',
    'Elephant Yam(Suran)/Amorphophallus': '01.1.7.5.9',
    'Field Pea': '01.1.7.6.5',
    'Fig(Anjura/Anjeer)': '01.1.6.1.4',
    'Fish': '01.1.3.1.9',
    'Foxtail Millet(Navane)': '01.1.1.1.5',
    'French Beans(Frasbean)': '01.1.7.3.2',
    'Galgal(Lemon)': '01.1.6.2.2',
    'Garlic': '01.1.7.4.2',
    'Ghee': '01.1.5.2.9',
    'Ginger(Dry)': '01.1.9.4.0',
    'Ginger(Green)': '01.1.9.4.0',
    'Goat': '01.1.2.1.3',
    'Gram Raw(Chholia)': '01.1.7.3.9',
    'Grapes': '01.1.6.5.1',
    'Green Avare(W)': '01.1.7.3.2',
    'Green Chilli': '01.1.7.2.1',
    'Green Gram Dal(Moong Dal)': '01.1.7.6.9',
    'Green Gram(Moong)(Whole)': '01.1.7.6.9',
    'Green Peas': '01.1.7.3.3',
    'Groundnut': '01.1.6.8.8',
    'Groundnut pods(raw)': '01.1.6.8.8',
    'Groundnut(Split)': '01.1.6.8.8',
    'Guar': '01.1.7.3.2',
    'Guava': '01.1.6.1.5',
    'Gur(Jaggery)': '01.1.8.2.0',
    'He Buffalo': '01.1.2.1.1',
    'Hen': '01.1.2.1.4',
    'Hybrid Cumbu': '01.1.1.1.5',
    'Indian Beans(Seam)': '01.1.7.3.2',
    'Jack Fruit(Ripe)': '01.1.6.1.9',
    'Jamun(Narale Hannu)': '01.1.6.4.9',
    'Jowar(Sorghum)': '01.1.1.1.3',
    'Kabuli Chana(Chickpeas-White)': '01.1.7.6.3',
    'Karbuja(Musk Melon)': '01.1.6.5.3',
    'Kinnow': '01.1.6.2.4',
    'Knool Khol': '01.1.7.1.9',
    'Kodo Millet(Varagu)': '01.1.1.1.5',
    'Kulthi(Horse Gram)': '01.1.7.6.9',
    'Kutki': '01.1.1.1.5',
    'Ladies Finger': '01.1.7.2.6',
    'Lak(Teora)': '01.1.7.6.9',
    'Leafy Vegetable': '01.1.7.1.9',
    'Lemon': '01.1.6.2.2',
    'Lentil(Masur)(Whole)': '01.1.7.6.4',
    'Lime': '01.1.6.2.2',
    'Litchi': '01.1.6.1.9',
    'Little gourd(Kundru)': '01.1.7.2.9',
    'Long Melon(Kakri)': '01.1.6.5.3',
    'Mace': '01.1.9.4.0',
    'Maida Atta': '01.1.1.2.1',
    'Maize': '01.1.1.1.6',
    'Mango': '01.1.6.1.5',
    'Mango(Raw-Ripe)': '01.1.6.1.5',
    'Marasebu': '01.1.6.3.2',
    'Mashrooms': '01.1.7.4.5',
    'Masur Dal': '01.1.7.6.4',
    'Mataki': '01.1.7.6.9',
    'Methi Seeds': '01.1.9.4.0',
    'Methi(Leaves)': '01.1.7.1.9',
    'Millets': '01.1.1.1.5',
    'Mint(Pudina)': '01.1.9.4.0',
    'Mousambi(Sweet Lime)': '01.1.6.2.9',
    'Mustard': '01.1.9.4.0',
    'Mustard Oil': '01.1.5.1.9',
    'Nutmeg': '01.1.9.4.0',
    'Onion': '01.1.7.4.3',
    'Onion Green': '01.1.7.4.4',
    'Orange': '01.1.6.2.3',
    'Other Pulses': '01.1.7.6.9',
    'Other green and fresh vegetables': '01.1.7.4.9',
    'Ox': '01.1.2.1.1',
    'Paddy(Basmati)': '01.1.1.1.2',
    'Paddy(Common)': '01.1.1.1.2',
    'Papaya': '01.1.6.1.6',
    'Papaya(Raw)': '01.1.6.1.6',
    'Patti Calcutta': '02.4.0.0',
    'Pea Pod/Pea Cod/हरी मटर': '01.1.7.3.3',
    'Peach': '01.1.6.3.5',
    'Pear(Marasebu)': '01.1.6.3.2',
    'Peas Wet': '01.1.7.3.3',
    'Peas(Dry)': '01.1.7.6.5',
    'Pegeon Pea(Arhar Fali)': '01.1.7.3.9',
    'Pepper garbled': '01.1.9.4.0',
    'Pepper ungarbled': '01.1.9.4.0',
    'Persimon(Japani Fal)': '01.1.6.5.5',
    'Pigs': '01.1.2.1.2',
    'Pineapple': '01.1.6.1.7',
    'Plum': '01.1.6.3.6',
    'Pointed gourd(Parval)': '01.1.7.2.9',
    'Pomegranate': '01.1.6.5.9',
    'Potato': '01.1.7.5.1',
    'Pumpkin': '01.1.7.2.5',
    'Raddish': '01.1.7.4.9',
    'Ragi(Finger Millet)': '01.1.1.1.5',
    'Rajgir': '01.1.1.1.9',
    'Ram': '01.1.2.1.3',
    'Raya': '01.1.9.4.0',
    'Red gram split/Arhar dal/Tur dal': '01.1.7.6.7',
    'Red gram/Arhar/Tur(whole)': '01.1.7.6.7',
    'Rice': '01.1.1.1.2',
    'Ridgeguard(Tori)': '01.1.7.2.5',
    'Round gourd': '01.1.7.2.5',
    'Sabu Dan': '01.1.7.9.1',
    'Saffron': '01.1.9.4.0',
    'Sajje': '01.1.1.1.5',
    'Same/Savi': '01.1.1.1.5',
    'Seemebadnekai': '01.1.7.2.9',
    'Seetapal': '01.1.6.1.9',
    'Sesamum(Sesame,Gingelly,Til)': '01.1.9.4.0',
    'She Buffalo': '01.1.2.1.1',
    'She Goat': '01.1.2.1.3',
    'Sheep': '01.1.2.1.3',
    'Snakeguard': '01.1.7.2.5',
    'Soanf': '01.1.9.4.0',
    'Sompu': '01.1.9.4.0',
    'Soyabean': '01.1.7.6.9',
    'Spinach': '01.1.7.1.5',
    'Spiny Gourd / Kartali(Kantola)': '01.1.7.2.9',
    'Sponge gourd': '01.1.7.2.5',
    'Squash(Chappal Kadoo)': '01.1.7.2.5',
    'Sugar': '01.1.8.1.1',
    'Surat Beans(Papadi)': '01.1.7.3.2',
    'Suva(Dill Seed)': '01.1.9.4.0',
    'Sweet Potato': '01.1.7.5.2',
    'Sweet Pumpkin': '01.1.7.2.5',
    'Tamarind Fruit': '01.1.6.7.9',
    'Tapioca': '01.1.7.5.3',
    'Tender Coconut': '01.1.6.1.8',
    'Thinai(Italian Millet)': '01.1.1.1.5',
    'Thogrikai': '01.1.7.3.9',
    'Thondekai': '01.1.7.2.9',
    'Tinda': '01.1.7.2.5',
    'Tobacco': '02.3.0.9',
    'Tomato': '01.1.7.2.4',
    'Turmeric': '01.1.9.4.0',
    'Turmeric(raw)': '01.1.9.4.0',
    'Turnip': '01.1.7.4.1',
    'Walnut': '01.1.6.8.6',
    'Water Melon': '01.1.6.5.4',
    'Wheat': '01.1.1.1.1',
    'Wheat Atta': '01.1.1.2.1',
    'White Peas': '01.1.7.6.5',
    'White Pumpkin': '01.1.7.2.5',
    'Yam': '01.1.7.5.4',
    'Yam(Ratalu)': '01.1.7.5.4',
    'basil': '01.1.9.4.0',
    'dried mango': '01.1.6.7.9',
    'mango powder': '01.1.9.4.0',
    'nigella': '01.1.9.4.0',
    'nigella seeds': '01.1.9.4.0',
    'poppy seeds': '01.1.9.4.0',
    'stevia': '01.1.8.2.0',
}

# Non-food agricultural commodities the mandis trade that fall outside COICOP
# 01/02 entirely: fibres, rubber, timber, fodder, green manure, oilseeds traded
# for crushing, cut flowers and medicinal roots. Listed explicitly so the
# absence of a code is a recorded decision rather than a gap in the table above.
# Tobacco and arecanut/betel DO have division-02 leaves and are in _COICOP_MAP.
_NON_FOOD_COMMODITIES: frozenset[str] = frozenset({
    'Absinthe', 'Ambady/Mesta/Patson', 'Antawala', 'Anthorium', 'Ashwagandha',
    'Astera', 'Bamboo', 'Broomstick(Flower Broom)', 'Carnation',
    'Chrysanthemum(Loose)', 'Coconut Seed', 'Cotton', 'Cotton Seed', 'Dhaincha',
    'Dry Fodder', 'Firewood', 'Giloy', 'Gladiolus Cut Flower', 'Green Fodder',
    'Ground Nut Seed', 'Guar Seed(Cluster Beans Seed)', 'Gurellu', 'Honge seed',
    'Indian Colza(Sarson)', 'Isabgul(Psyllium)', 'Jarbara', 'Jasmine', 'Jute',
    'Kakada', 'Kankambra', 'Lilly', 'Linseed', 'Lint', 'Lotus', 'Lotus Sticks',
    'Mahedi', 'Mahua', 'Mahua Seed(Hippe seed)', 'Marigold(Calcutta)',
    'Marigold(loose)', 'Muesli', 'Muleti', 'Myrobolan(Harad)', 'Neem Seed',
    'Niger Seed(Ramtil)', 'Orchid', 'Raibel', 'Rose(Local)', 'Rose(Loose))',
    'Rubber', 'Safflower', 'Sanai/Sunhemp', 'Soapnut(Antawala/Retha)', 'Sugarcane',
    'Sunflower/Sunflower Seed', 'Tamarind Seed', 'Taramira', 'Tube Flower',
    'Tube Rose(Double)', 'Tube Rose(Loose)', 'Tube Rose(Single)', 'Tulip',
    'White Muesli', 'Wood', 'dhawai flowers', 'karanja seeds', 'sanay'
})


def _coicop_for(commodity: str) -> str | None:
    """Curated leaf for a mandi commodity, or None to defer to the classifier."""
    if commodity in _NON_FOOD_COMMODITIES:
        return None
    return _COICOP_MAP.get(commodity)


def _num(val) -> float | None:
    try:
        f = float(str(val).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return f if f > 0 else None


def _fetch_day(session, day: date) -> list[dict]:
    date_str = day.strftime("%d/%m/%Y")
    records: list[dict] = []
    offset = 0
    while True:
        try:
            resp = session.get(
                _API_URL,
                params={
                    "api-key": _API_KEY,
                    "format": "json",
                    "limit": _LIMIT,
                    "offset": offset,
                    "filters[Arrival_Date]": date_str,
                },
                timeout=60,
            )
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] fetch failed for %s: %s", _SOURCE_KEY, date_str, exc)
            break
        batch = payload.get("records") or []
        records.extend(batch)
        total = int(payload.get("total") or 0)
        offset += len(batch)
        if not batch or offset >= total:
            break
        time.sleep(2)
    return records


def _rows_for_day(session, day: date) -> list[dict]:
    ts = get_scrape_ts()
    out: list[dict] = []
    for rec in _fetch_day(session, day):
        commodity = str(rec.get("Commodity") or "").strip()
        if not commodity:
            continue
        price = _num(rec.get("Modal_Price"))
        if price is None:
            continue
        variety = str(rec.get("Variety") or "").strip()
        same_as_commodity = variety.lower() == commodity.lower()
        item_name = (
            commodity
            if variety.lower() in _EMPTY_VARIETY or same_as_commodity
            else f"{commodity} ({variety})"
        )
        market = str(rec.get("Market") or "").strip()
        grade = str(rec.get("Grade") or "").strip()
        state = str(rec.get("State") or "").strip()
        district = str(rec.get("District") or "").strip()
        min_p = _num(rec.get("Min_Price"))
        max_p = _num(rec.get("Max_Price"))
        # NOTE: PriceObservation's optional geographic columns (subnational_area,
        # city, district) are documented in fetcher_pattern.md but writers.py's
        # PRICE_COLUMNS does not include them -- any fetcher that sets them has
        # those values silently dropped on write. State/district/market survive
        # here only via `notes`.
        row = {
            "observation_date": day.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": item_name,
            "coicop_code": _coicop_for(commodity),
            "price_local": round(price, 2),
            "currency": _CURRENCY,
            "unit": _UNIT,
            "market": market,
            "grade": grade,
            "source_url": _RESOURCE_PAGE,
            "notes": (
                f"state={state or 'n/a'}; district={district or 'n/a'}; "
                f"market={market or 'n/a'}; grade={grade or 'n/a'}; "
                f"min={min_p}; max={max_p} Rs./Quintal"
            ),
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        row.pop("market")
        row.pop("grade")
        out.append(row)
    return out


def fetch_in_agmarknet(cutoff: date) -> pd.DataFrame | None:
    # The shared data.gov.in sample api-key throttles under burst load (429s
    # observed after a handful of rapid calls, clearing after ~20-40s); a
    # generous retry/backoff plus a deliberate pause between days keeps this
    # fetcher under that ceiling instead of tripping it every run.
    session = get_session(retries=8, backoff=3.0)
    today = date.today()
    all_rows: list[dict] = []
    for i in range(_MAX_DAYS_BACK):
        day = today - timedelta(days=i)
        if day <= cutoff:
            break
        day_rows = _rows_for_day(session, day)
        logger.info("[%s] %s -> %d rows", _SOURCE_KEY, day, len(day_rows))
        all_rows.extend(day_rows)
        time.sleep(2)
    logger.info("[%s] %d total rows (cutoff=%s)", _SOURCE_KEY, len(all_rows), cutoff)
    return pd.DataFrame(all_rows) if all_rows else None
