"""World Bank RTDI food prices (microdata.worldbank.org) — 40 countries.

The Real-Time Development Indicators collection publishes monthly food price
levels per commodity per market, reaching back to 2007 — roughly a decade
further than anything the retail scrapers can reach, since Common Crawl and
Wayback both thin out badly before 2016.

**Thirty-seven of the forty countries live in one study**, the global panel
(catalog 4483, ~1.1 GB uncompressed, 3,128 markets). Its per-country slices are
byte-identical to the standalone country studies, so downloading it once and
slicing it is strictly better than forty downloads. ``_load_global`` caches the
parsed frame for the life of the process, and ``collect`` runs fetchers
sequentially in one process, so a whole-collection run pays the download once.
Philippines, Syria and Yemen are absent from the global panel and keep their own
studies.

Unlike WFP, this feed carries its COICOP **per item**, from ``_ITEMS`` below,
rather than deferring to the classifier. Two reasons. The vocabulary is a closed
controlled set, small enough to map by hand and audit by eye. And the tickers are
bare commodity nouns — ``rice``, ``oil`` — which is the input the classifier is
weakest on, having no brand, pack size or retailer context to work from.

**The mapping keys on (iso3, ticker), never ticker alone.** One token covers
different products in different countries: ``oil`` is vegetable in Indonesia,
soybean in Lao PDR and palm in Myanmar — three distinct leaves of 01.1.5. Across
all forty countries ``rice`` carries eighteen distinct specifications and ``oil``
ten. The ``full_name`` column in each study's ticker_info is what disambiguates
them, and it is recorded beside every entry below.

Four kinds of column look usable and are not:

- ``food_price_index`` is an INDEX (Jan 2018 = 1), not a level. It is the only
  ticker present in all forty studies, so it is also the easiest to include by
  accident. Excluded by omission from ``_ITEMS``.
- bare ``<ticker>`` columns are the raw survey observations, sparse by design
  (14,698 of 52,628 for Indonesian rice). The ``c_<ticker>`` close series is the
  dense model-completed estimate, and is what we read.
- ``exchange_rate_unofficial``, the ``wage_*`` and ``milling_cost_*`` series and
  the ``fuel_*`` tickers are not food. The fuels are division 07 and would be
  dropped by the build's division filter anyway.
- **a ``_fao`` ticker is not a separate commodity.** It is the same good sourced
  from FAO rather than the national statistics office, and forty-five country
  commodities carry both. Worse, the two often use different bases: twelve pairs
  price the national series per kg and the FAO twin per 100 kg, which puts the
  values a factor of 100 apart. Emitting both would double-count every one of
  those observations at two incompatible scales, so ``_ITEMS`` keeps the national
  ticker where one exists and falls back to ``_fao`` only where it does not.

Units are passed through as the study writes them; ``parse_declared_unit`` folds
case, so "KG", "Kg", "L" and pack forms like "400 G" or "3.5 KG" all resolve.
Three groups do not resolve and yield observations without unit values: bare
counts ("Unit", "1 unit", "30 pcs"), imperial measures ("6 lbs", "100 Pounds",
"Gallon" — convertible in principle, but the parser has no imperial support),
and the Haitian "Marmite". They are mapped rather than dropped because the price
is real and the leaf is right.

Live animals sold by the head (the ``livestock_*`` tickers) are excluded: a goat
on the hoof is not a retail food purchase.

Five mapped tickers are declared in a study's ticker_info but have no column in
the panel it ships — Gambian ``meat_sheep``, and ``batteries``, ``candles``,
``charcoal`` and ``soap`` for Guinea-Bissau. They are kept, so the mapping is
already right if the series appears, and each logs one "absent from panel"
warning per run. That warning is expected for these five and means the
publisher's metadata and data disagree, not that anything here is broken.

Per-market rows are kept rather than collapsed to a national average. They share
one ``input_hash`` — identity is (item_name, source_url), and the URL is the
study, so every market of a given item resolves to a single classification —
while all of them survive into the observations frame, where they give each
(leaf, country, unit) cell real support instead of one row a month.
"""

from __future__ import annotations

import io
import logging
import re
import zipfile
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_BASE = "https://microdata.worldbank.org"
_IDENT = ["source_key", "observation_date", "item_name", "subnational_area"]

# Every weekly vintage is exposed at once and the newest is listed first;
# three files per vintage means the data file is always within the first few.
_MAX_PROBES = 12

# The global panel: 37 countries in one study.
_GLOBAL_CATALOG = 4483

# iso3 -> (display country, catalog id or None when the country is in the
# global panel). Display names are the study's own.
_COUNTRIES: dict[str, tuple[str, int | None]] = {
    "idn": ("Indonesia", None),  # eap/indonesia
    "lao": ("Lao PDR", None),  # eap/lao_pdr
    "mmr": ("Myanmar", None),  # eap/myanmar
    "phl": ("Philippines", 6172),  # eap/philippines
    "arm": ("Armenia", None),  # eca/armenia
    "gtm": ("Guatemala", None),  # lac/guatemala
    "hti": ("Haiti", None),  # lac/haiti
    "afg": ("Afghanistan", None),  # menaap/afghanistan
    "irq": ("Iraq", None),  # menaap/iraq
    "lbn": ("Lebanon", None),  # menaap/lebanon
    "lby": ("Libya", None),  # menaap/libya
    "syr": ("Syrian Arab Republic", 4507),  # menaap/syria
    "yem": ("Yemen, Rep.", 4508),  # menaap/yemen
    "bgd": ("Bangladesh", None),  # sar/bangladesh
    "lka": ("Sri Lanka", None),  # sar/sri_lanka
    "bfa": ("Burkina Faso", None),  # ssa/burkina_faso
    "bdi": ("Burundi", None),  # ssa/burundi
    "cmr": ("Cameroon", None),  # ssa/cameroon
    "caf": ("Central African Republic", None),  # ssa/central_african_republic
    "tcd": ("Chad", None),  # ssa/chad
    "cod": ("Congo, Dem. Rep.", None),  # ssa/congo_dem_rep
    "cog": ("Congo, Rep.", None),  # ssa/congo_rep
    "eth": ("Ethiopia", None),  # ssa/ethiopia
    "gmb": ("Gambia, The", None),  # ssa/gambia
    "gin": ("Guinea", None),  # ssa/guinea
    "gnb": ("Guinea-Bissau", None),  # ssa/guinea_bissau
    "ken": ("Kenya", None),  # ssa/kenya
    "lbr": ("Liberia", None),  # ssa/liberia
    "mdg": ("Madagascar", None),  # ssa/madagascar
    "mwi": ("Malawi", None),  # ssa/malawi
    "mli": ("Mali", None),  # ssa/mali
    "mrt": ("Mauritania", None),  # ssa/mauritania
    "moz": ("Mozambique", None),  # ssa/mozambique
    "ner": ("Niger", None),  # ssa/niger
    "nga": ("Nigeria", None),  # ssa/nigeria
    "sen": ("Senegal", None),  # ssa/senegal
    "som": ("Somalia", None),  # ssa/somalia
    "ssd": ("South Sudan", None),  # ssa/south_sudan
    "sdn": ("Sudan", None),  # ssa/sudan
    "uga": ("Uganda", None),  # ssa/uganda
}

# (iso3, ticker) -> (COICOP leaf, the study's own unit, the study's own
# full_name). Every code is a deepest leaf of the repo taxonomy: division 01
# leaves carry five dotted levels, every other division four. A code that is
# not a leaf fails `coicop_codes.is_narrow` SILENTLY and falls through to the
# classifier, so `test_wb_rtdi_prices` asserts every entry here resolves.
_ITEMS: dict[tuple[str, str], tuple[str, str, str]] = {
    # --- Indonesia (IDN) -------------------------------------------
    ("idn", "eggs"): ("01.1.4.8.1", "KG", "Eggs"),
    ("idn", "garlic"): ("01.1.7.4.2", "KG", "Garlic (medium)"),
    ("idn", "meat_beef"): ("01.1.2.2.1", "KG", "Meat (beef, first quality)"),
    ("idn", "meat_chicken"): ("01.1.2.2.4", "KG", "Meat (chicken)"),
    ("idn", "meat_chicken_broiler"): ("01.1.2.2.4", "KG", "Meat (chicken, broiler)"),
    ("idn", "oil"): ("01.1.5.1.9", "KG", "Oil (vegetable)"),
    ("idn", "onions"): ("01.1.7.4.3", "KG", "Onions (shallot, medium)"),
    ("idn", "rice"): ("01.1.1.1.2", "KG", "Rice (medium quality)"),
    ("idn", "sugar"): ("01.1.8.1.1", "KG", "Sugar (local)"),
    # --- Lao PDR (LAO) ---------------------------------------------
    ("lao", "eggs"): ("01.1.4.8.1", "Unit", "Eggs"),
    ("lao", "fish_catfish"): ("01.1.3.1.1", "KG", "Fish (catfish)"),
    ("lao", "fish_tilapia"): ("01.1.3.1.1", "KG", "Fish (tilapia, farmed)"),
    ("lao", "garlic"): ("01.1.7.4.2", "KG", "Garlic (small)"),
    ("lao", "meat_beef"): ("01.1.2.2.1", "KG", "Meat (beef, first quality)"),
    ("lao", "meat_buffalo"): ("01.1.2.2.1", "KG", "Meat (buffalo, first quality)"),
    ("lao", "meat_chicken"): ("01.1.2.2.4", "KG", "Meat (chicken)"),
    ("lao", "meat_pork"): ("01.1.2.2.2", "KG", "Meat (pork, second quality)"),
    ("lao", "oil"): ("01.1.5.1.4", "L", "Oil (soybean)"),
    ("lao", "rice"): ("01.1.1.1.2", "KG", "Rice (glutinous, second quality)"),
    ("lao", "sugar"): ("01.1.8.1.1", "KG", "Sugar (brown)"),
    # --- Myanmar (MMR) ---------------------------------------------
    ("mmr", "oil"): ("01.1.5.1.2", "L", "Oil (palm)"),
    ("mmr", "onions"): ("01.1.7.4.3", "KG", "Onions (local)"),
    ("mmr", "pulses"): ("01.1.7.6.9", "KG", "Pulses"),
    ("mmr", "rice"): ("01.1.1.1.2", "KG", "Rice (low quality)"),
    ("mmr", "salt"): ("01.1.9.3.1", "KG", "Salt"),
    # --- Philippines (PHL) -----------------------------------------
    ("phl", "beans"): ("01.1.7.6.1", "KG", "Beans (mung)"),
    ("phl", "cabbage"): ("01.1.7.1.2", "KG", "Cabbage"),
    ("phl", "carrots"): ("01.1.7.4.1", "KG", "Carrots"),
    ("phl", "eggs"): ("01.1.4.8.1", "Unit", "Eggs"),
    ("phl", "garlic"): ("01.1.7.4.2", "KG", "Garlic"),
    ("phl", "onions"): ("01.1.7.4.3", "KG", "Onions (red)"),
    ("phl", "potatoes"): ("01.1.7.5.2", "KG", "Sweet potatoes"),
    ("phl", "rice"): ("01.1.1.1.2", "KG", "Rice (regular, milled)"),
    ("phl", "tomatoes"): ("01.1.7.2.4", "KG", "Tomatoes"),
    # --- Armenia (ARM) ---------------------------------------------
    ("arm", "apples"): ("01.1.6.3.1", "KG", "Apples (red)"),
    ("arm", "bread"): ("01.1.1.3.1", "KG", "Bread (high grade flour)"),
    ("arm", "cabbage"): ("01.1.7.1.2", "KG", "Cabbage"),
    ("arm", "carrots"): ("01.1.7.4.1", "KG", "Carrots"),
    ("arm", "cheese"): ("01.1.4.5.0", "KG", "Cheese (dry)"),
    ("arm", "cucumbers"): ("01.1.7.2.2", "KG", "Cucumbers (greenhouse)"),
    ("arm", "eggs"): ("01.1.4.8.1", "Unit", "Eggs"),
    ("arm", "fish"): ("01.1.3.1.9", "KG", "Fish (fresh)"),
    ("arm", "lentils"): ("01.1.7.6.4", "KG", "Lentils"),
    ("arm", "meat_beef"): ("01.1.2.2.1", "KG", "Meat (beef)"),
    ("arm", "meat_chicken"): ("01.1.2.2.4", "KG", "Meat (chicken)"),
    ("arm", "meat_pork"): ("01.1.2.2.2", "KG", "Meat (pork)"),
    ("arm", "milk"): ("01.1.4.1.1", "L", "Milk"),
    ("arm", "oil"): ("01.1.5.1.9", "L", "Oil (vegetable)"),
    ("arm", "onions"): ("01.1.7.4.3", "KG", "Onions"),
    ("arm", "pasta"): ("01.1.1.5.0", "KG", "Pasta"),
    ("arm", "potatoes"): ("01.1.7.5.1", "KG", "Potatoes"),
    ("arm", "rice"): ("01.1.1.1.2", "KG", "Rice (white)"),
    ("arm", "sugar"): ("01.1.8.1.1", "KG", "Sugar"),
    ("arm", "tomatoes"): ("01.1.7.2.4", "KG", "Tomatoes"),
    ("arm", "wheat_flour"): ("01.1.1.2.1", "KG", "Wheat flour"),
    # --- Guatemala (GTM) -------------------------------------------
    ("gtm", "beans"): ("01.1.7.6.1", "100 Pounds", "Beans (black)"),
    ("gtm", "carrots"): ("01.1.7.4.1", "13.92 KG", "Carrots"),
    ("gtm", "maize"): ("01.1.1.1.6", "100 Pounds", "Maize (yellow)"),
    ("gtm", "onions"): ("01.1.7.4.3", "50 pcs", "Onions (white)"),
    ("gtm", "rice"): ("01.1.1.1.2", "100 Pounds", "Rice (high quality)"),
    # --- Haiti (HTI) -----------------------------------------------
    ("hti", "beans_fao"): ("01.1.7.6.1", "6 lbs", "Beans (black)"),
    ("hti", "maize_meal"): ("01.1.1.2.6", "Marmite", "Maize meal (local)"),
    ("hti", "oil"): ("01.1.5.1.9", "Gallon", "Oil (vegetable, imported)"),
    ("hti", "pasta"): ("01.1.1.5.0", "350 G", "Pasta"),
    ("hti", "rice_fao"): ("01.1.1.1.2", "6 lbs", "Rice"),
    ("hti", "sorghum_fao"): ("01.1.1.1.3", "6 lbs", "Sorghum"),
    ("hti", "sugar"): ("01.1.8.1.1", "Marmite", "Sugar (white)"),
    ("hti", "wheat_fao"): ("01.1.1.1.1", "6 lbs", "Wheat"),
    ("hti", "wheat_flour"): ("01.1.1.2.1", "Marmite", "Wheat flour (imported)"),
    # --- Afghanistan (AFG) -----------------------------------------
    ("afg", "bread"): ("01.1.1.3.1", "KG", "Bread"),
    ("afg", "oil"): ("01.1.5.1.9", "KG", "Oil (cooking)"),
    ("afg", "pulses"): ("01.1.7.6.9", "KG", "Pulses"),
    ("afg", "rice"): ("01.1.1.1.2", "KG", "Rice (low quality)"),
    ("afg", "salt"): ("01.1.9.3.1", "KG", "Salt"),
    ("afg", "sugar"): ("01.1.8.1.1", "KG", "Sugar"),
    ("afg", "wheat"): ("01.1.1.1.1", "KG", "Wheat"),
    ("afg", "wheat_flour"): ("01.1.1.2.1", "KG", "Wheat flour (high quality)"),
    ("afg", "wheat_flour_low_price_fao"): (
        "01.1.1.2.1",
        "Kg",
        "Wheat (flour, low price)",
    ),
    # --- Iraq (IRQ) ------------------------------------------------
    ("irq", "beans"): ("01.1.7.6.1", "KG", "Beans (white)"),
    ("irq", "bread_fao"): ("01.1.1.3.1", "1 unit", "Bread (Khoboz)"),
    ("irq", "cheese"): ("01.1.4.5.0", "KG", "Cheese (local)"),
    ("irq", "dates"): ("01.1.6.1.3", "KG", "Dates"),
    ("irq", "eggs_fao"): ("01.1.4.8.1", "1 unit", "Eggs"),
    ("irq", "fish"): ("01.1.3.1.9", "KG", "Fish"),
    ("irq", "lentils"): ("01.1.7.6.4", "KG", "Lentils"),
    ("irq", "meat_beef"): ("01.1.2.2.1", "KG", "Meat (beef)"),
    ("irq", "meat_chicken"): ("01.1.2.2.4", "KG", "Meat (chicken)"),
    ("irq", "milk"): ("01.1.4.1.1", "L", "Milk"),
    ("irq", "oil"): ("01.1.5.1.9", "L", "Oil (vegetable)"),
    ("irq", "potatoes"): ("01.1.7.5.1", "KG", "Potatoes"),
    ("irq", "rice"): ("01.1.1.1.2", "KG", "Rice"),
    ("irq", "salt"): ("01.1.9.3.1", "KG", "Salt (iodised)"),
    ("irq", "sugar"): ("01.1.8.1.1", "KG", "Sugar"),
    ("irq", "tea"): ("01.2.3.0.2", "KG", "Tea"),
    ("irq", "tomatoes"): ("01.1.7.2.4", "KG", "Tomatoes"),
    ("irq", "wheat_flour"): ("01.1.1.2.1", "KG", "Wheat flour"),
    # --- Lebanon (LBN) ---------------------------------------------
    ("lbn", "cabbage"): ("01.1.7.1.2", "KG", "Cabbage"),
    ("lbn", "cucumbers"): ("01.1.7.2.2", "KG", "Cucumbers (greenhouse)"),
    ("lbn", "eggs"): ("01.1.4.8.1", "30 pcs", "Eggs"),
    ("lbn", "oil"): ("01.1.5.1.1", "5 L", "Oil (sunflower)"),
    ("lbn", "rice"): ("01.1.1.1.2", "900 G", "Rice (imported, Egyptian)"),
    ("lbn", "wheat_flour"): ("01.1.1.2.1", "900 G", "Wheat flour"),
    # --- Libya (LBY) -----------------------------------------------
    ("lby", "beans"): ("01.1.7.6.1", "400 G", "Beans"),
    ("lby", "bread"): ("01.1.1.3.1", "5 pcs", "Bread"),
    ("lby", "chickpeas"): ("01.1.7.6.3", "400 G", "Chickpeas"),
    ("lby", "chili"): ("01.1.7.2.1", "KG", "Chili (green)"),
    ("lby", "couscous"): ("01.1.1.5.0", "KG", "Couscous"),
    ("lby", "eggs"): ("01.1.4.8.1", "30 pcs", "Eggs"),
    ("lby", "fish_tuna_canned"): ("01.1.3.3.1", "200 G", "Fish (tuna, canned)"),
    ("lby", "meat_chicken"): ("01.1.2.2.4", "KG", "Meat (chicken)"),
    ("lby", "meat_lamb"): ("01.1.2.2.3", "KG", "Meat (lamb)"),
    ("lby", "milk"): ("01.1.4.1.1", "L", "Milk (pasteurized)"),
    ("lby", "oil"): ("01.1.5.1.9", "L", "Oil (vegetable)"),
    ("lby", "onions"): ("01.1.7.4.3", "KG", "Onions"),
    ("lby", "pasta"): ("01.1.1.5.0", "500 G", "Pasta"),
    ("lby", "potatoes"): ("01.1.7.5.1", "KG", "Potatoes"),
    ("lby", "rice"): ("01.1.1.1.2", "KG", "Rice"),
    ("lby", "salt"): ("01.1.9.3.1", "KG", "Salt"),
    ("lby", "sugar"): ("01.1.8.1.1", "KG", "Sugar"),
    ("lby", "tea"): ("01.2.3.0.2", "250 G", "Tea (black)"),
    ("lby", "tomatoes"): ("01.1.7.2.4", "KG", "Tomatoes"),
    ("lby", "tomatoes_paste"): ("01.1.7.9.9", "400 G", "Tomatoes (paste)"),
    ("lby", "wheat_flour"): ("01.1.1.2.1", "KG", "Wheat flour"),
    # --- Syrian Arab Republic (SYR) --------------------------------
    ("syr", "apples"): ("01.1.6.3.1", "KG", "Apples"),
    ("syr", "bananas"): ("01.1.6.1.2", "KG", "Bananas"),
    ("syr", "beans"): ("01.1.7.6.1", "KG", "Beans (white)"),
    ("syr", "bread"): ("01.1.1.3.1", "1.1 KG", "Bread (bakery)"),
    ("syr", "bulgur"): ("01.1.1.1.1", "KG", "Bulgur"),
    ("syr", "carrots"): ("01.1.7.4.1", "KG", "Carrots"),
    ("syr", "cheese"): ("01.1.4.5.0", "KG", "Cheese"),
    ("syr", "chickpeas"): ("01.1.7.6.3", "KG", "Chickpeas"),
    ("syr", "dates"): ("01.1.6.1.3", "KG", "Dates"),
    ("syr", "eggplants"): ("01.1.7.2.3", "KG", "Eggplants"),
    ("syr", "eggs"): ("01.1.4.8.1", "30 pcs", "Eggs"),
    ("syr", "fish_tuna_canned"): ("01.1.3.3.1", "160 G", "Fish (tuna, canned)"),
    ("syr", "lentils"): ("01.1.7.6.4", "KG", "Lentils"),
    ("syr", "meat_beef_minced"): ("01.1.2.2.1", "KG", "Meat (beef, minced)"),
    ("syr", "meat_chicken_plucked"): ("01.1.2.2.4", "KG", "Meat (chicken, plucked)"),
    ("syr", "oil"): ("01.1.5.1.9", "L", "Oil"),
    ("syr", "parsley"): ("01.1.9.4.0", "Packet", "Parsley"),
    ("syr", "potatoes"): ("01.1.7.5.1", "KG", "Potatoes"),
    ("syr", "rice"): ("01.1.1.1.2", "KG", "Rice"),
    ("syr", "salt"): ("01.1.9.3.1", "KG", "Salt (iodised)"),
    ("syr", "sugar"): ("01.1.8.1.1", "KG", "Sugar"),
    ("syr", "tomatoes"): ("01.1.7.2.4", "KG", "Tomatoes"),
    ("syr", "wheat_flour"): ("01.1.1.2.1", "KG", "Wheat flour"),
    ("syr", "yogurt"): ("01.1.4.6.0", "KG", "Yogurt"),
    # --- Yemen, Rep. (YEM) -----------------------------------------
    ("yem", "beans"): ("01.1.7.6.1", "KG", "Beans (white)"),
    ("yem", "eggs"): ("01.1.4.8.1", "Unit", "Eggs"),
    ("yem", "lentils"): ("01.1.7.6.4", "KG", "Lentils"),
    ("yem", "meat_chicken_fao"): ("01.1.2.2.4", "Kg", "Meat (Chicken,)"),
    ("yem", "meat_mutton_fao"): ("01.1.2.2.3", "Kg", "Meat (Mutton)"),
    ("yem", "millet_fao"): ("01.1.1.1.5", "Kg", "Millet"),
    ("yem", "oil"): ("01.1.5.1.9", "L", "Oil (vegetable)"),
    ("yem", "onions"): ("01.1.7.4.3", "KG", "Onions"),
    ("yem", "peas"): ("01.1.7.6.5", "KG", "Peas (yellow, split)"),
    ("yem", "potatoes"): ("01.1.7.5.1", "KG", "Potatoes"),
    ("yem", "rice"): ("01.1.1.1.2", "KG", "Rice (imported)"),
    ("yem", "salt"): ("01.1.9.3.1", "KG", "Salt"),
    ("yem", "sorghum_fao"): ("01.1.1.1.3", "Kg", "Sorghum"),
    ("yem", "sugar"): ("01.1.8.1.1", "KG", "Sugar"),
    ("yem", "tomatoes"): ("01.1.7.2.4", "KG", "Tomatoes"),
    ("yem", "wheat"): ("01.1.1.1.1", "KG", "Wheat"),
    ("yem", "wheat_flour"): ("01.1.1.2.1", "KG", "Wheat flour"),
    # --- Bangladesh (BGD) ------------------------------------------
    ("bgd", "lentils"): ("01.1.7.6.4", "KG", "Lentils (masur)"),
    ("bgd", "oil"): ("01.1.5.1.2", "L", "Oil (palm)"),
    ("bgd", "rice"): ("01.1.1.1.2", "KG", "Rice (coarse)"),
    ("bgd", "wheat_flour"): ("01.1.1.2.1", "KG", "Wheat flour"),
    # --- Sri Lanka (LKA) -------------------------------------------
    ("lka", "rice_fao"): ("01.1.1.1.2", "Kg", "Rice (white)"),
    ("lka", "rice_various"): ("01.1.1.1.2", "KG", "Rice Various"),
    ("lka", "wheat_flour"): ("01.1.1.2.1", "KG", "Wheat flour"),
    # --- Burkina Faso (BFA) ----------------------------------------
    ("bfa", "beans"): ("01.1.7.6.6", "KG", "Beans (niebe)"),
    ("bfa", "maize"): ("01.1.1.1.6", "KG", "Maize (white)"),
    ("bfa", "millet"): ("01.1.1.1.5", "KG", "Millet"),
    ("bfa", "rice"): ("01.1.1.1.2", "KG", "Rice (imported)"),
    ("bfa", "sorghum"): ("01.1.1.1.3", "KG", "Sorghum (white)"),
    # --- Burundi (BDI) ---------------------------------------------
    ("bdi", "bananas"): ("01.1.6.1.2", "KG", "Bananas"),
    ("bdi", "beans"): ("01.1.7.6.1", "KG", "Beans"),
    ("bdi", "cassava_flour"): ("01.1.7.9.1", "KG", "Cassava flour"),
    ("bdi", "maize"): ("01.1.1.1.6", "KG", "Maize (white)"),
    ("bdi", "maize_flour"): ("01.1.1.2.6", "KG", "Maize flour"),
    ("bdi", "meat_goat"): ("01.1.2.2.3", "KG", "Meat (goat)"),
    ("bdi", "onions"): ("01.1.7.4.3", "KG", "Onions"),
    ("bdi", "potatoes"): ("01.1.7.5.2", "KG", "Sweet potatoes"),
    ("bdi", "rice"): ("01.1.1.1.2", "KG", "Rice (low quality, local)"),
    ("bdi", "tomatoes"): ("01.1.7.2.4", "KG", "Tomatoes"),
    # --- Cameroon (CMR) --------------------------------------------
    ("cmr", "bananas"): ("01.1.6.1.2", "12 KG", "Bananas"),
    ("cmr", "beans_fao"): ("01.1.7.6.1", "Kg", "Beans (red)"),
    ("cmr", "cassava"): ("01.1.7.5.3", "5 KG", "Cassava (fresh)"),
    ("cmr", "cocoyam_fao"): ("01.1.7.5.5", "Kg", "Cocoyam"),
    ("cmr", "fish_mackerel"): ("01.1.3.1.6", "KG", "Fish (mackerel, fresh)"),
    ("cmr", "maize"): ("01.1.1.1.6", "KG", "Maize (white)"),
    ("cmr", "meat_beef"): ("01.1.2.2.1", "KG", "Meat (beef)"),
    ("cmr", "oil"): ("01.1.5.1.2", "L", "Oil (palm)"),
    ("cmr", "plantains_fao"): ("01.1.7.5.7", "Kg", "Plantains"),
    ("cmr", "potatoes_fao"): ("01.1.7.5.1", "Kg", "Potatoes"),
    ("cmr", "rice"): ("01.1.1.1.2", "KG", "Rice (long grain, imported)"),
    ("cmr", "wheat_flour"): ("01.1.1.2.1", "KG", "Wheat flour"),
    # --- Central African Republic (CAF) ----------------------------
    ("caf", "cassava"): ("01.1.7.7.0", "KG", "Cassava (cossette)"),
    ("caf", "groundnuts"): ("01.1.6.8.8", "KG", "Groundnuts (shelled)"),
    ("caf", "maize"): ("01.1.1.1.6", "KG", "Maize"),
    ("caf", "meat_beef"): ("01.1.2.2.1", "KG", "Meat (beef)"),
    ("caf", "oil"): ("01.1.5.1.2", "L", "Oil (palm)"),
    ("caf", "rice"): ("01.1.1.1.2", "KG", "Rice"),
    ("caf", "sesame"): ("01.1.9.4.0", "KG", "Sesame"),
    ("caf", "sorghum"): ("01.1.1.1.3", "KG", "Sorghum"),
    # --- Chad (TCD) ------------------------------------------------
    ("tcd", "cassava"): ("01.1.7.7.0", "KG", "Cassava (cossette)"),
    ("tcd", "dates"): ("01.1.6.1.3", "KG", "Dates"),
    ("tcd", "fish"): ("01.1.3.2.9", "KG", "Fish (dry)"),
    ("tcd", "garlic"): ("01.1.7.4.2", "KG", "Garlic"),
    ("tcd", "maize"): ("01.1.1.1.6", "KG", "Maize (white)"),
    ("tcd", "millet"): ("01.1.1.1.5", "KG", "Millet"),
    ("tcd", "oil"): ("01.1.5.1.5", "L", "Oil (groundnut)"),
    ("tcd", "okra"): ("01.1.7.7.0", "KG", "Okra (dry)"),
    ("tcd", "onions"): ("01.1.7.4.3", "KG", "Onions (red)"),
    ("tcd", "pasta"): ("01.1.1.5.0", "KG", "Pasta"),
    ("tcd", "potatoes"): ("01.1.7.5.2", "KG", "Sweet potatoes"),
    ("tcd", "rice"): ("01.1.1.1.2", "KG", "Rice (imported)"),
    ("tcd", "salt"): ("01.1.9.3.1", "KG", "Salt"),
    ("tcd", "sorghum"): ("01.1.1.1.3", "KG", "Sorghum (red)"),
    ("tcd", "sugar"): ("01.1.8.1.1", "KG", "Sugar"),
    ("tcd", "tomatoes"): ("01.1.7.7.0", "KG", "Tomatoes (dried)"),
    # --- Congo, Dem. Rep. (COD) ------------------------------------
    ("cod", "beans"): ("01.1.7.6.1", "KG", "Beans"),
    ("cod", "cassava"): ("01.1.7.7.0", "KG", "Cassava (cossette)"),
    ("cod", "cassava_flour"): ("01.1.7.9.1", "KG", "Cassava flour"),
    ("cod", "fish"): ("01.1.3.1.9", "KG", "Fish (fresh)"),
    ("cod", "fish_salted"): ("01.1.3.2.9", "KG", "Fish (salted)"),
    ("cod", "fish_smoked"): ("01.1.3.2.9", "KG", "Fish (smoked)"),
    ("cod", "maize"): ("01.1.1.1.6", "KG", "Maize"),
    ("cod", "meat_beef"): ("01.1.2.2.1", "KG", "Meat (beef)"),
    ("cod", "meat_goat"): ("01.1.2.2.3", "KG", "Meat (goat, with bones)"),
    ("cod", "oil"): ("01.1.5.1.2", "L", "Oil (palm)"),
    ("cod", "plantains"): ("01.1.7.5.7", "KG", "Plantains"),
    ("cod", "rice"): ("01.1.1.1.2", "KG", "Rice (local)"),
    ("cod", "salt"): ("01.1.9.3.1", "KG", "Salt"),
    ("cod", "sugar"): ("01.1.8.1.1", "KG", "Sugar"),
    ("cod", "wheat_flour"): ("01.1.1.2.1", "KG", "Wheat flour"),
    # --- Congo, Rep. (COG) -----------------------------------------
    ("cog", "beans"): ("01.1.7.6.1", "KG", "Beans (white)"),
    ("cog", "cassava_flour"): ("01.1.7.9.1", "KG", "Cassava flour"),
    ("cog", "oil"): ("01.1.5.1.9", "L", "Oil (vegetable)"),
    ("cog", "rice"): ("01.1.1.1.2", "KG", "Rice (mixed, low quality)"),
    # --- Ethiopia (ETH) --------------------------------------------
    ("eth", "maize"): ("01.1.1.1.6", "100 KG", "Maize (white)"),
    ("eth", "pasta"): ("01.1.1.5.0", "KG", "Pasta"),
    ("eth", "sorghum"): ("01.1.1.1.3", "KG", "Sorghum"),
    ("eth", "teff_fao"): ("01.1.1.1.8", "100 kg", "Teff (mixed)"),
    ("eth", "wheat"): ("01.1.1.1.1", "100 KG", "Wheat"),
    # --- Gambia, The (GMB) -----------------------------------------
    ("gmb", "apples"): ("01.1.6.3.1", "KG", "Apples (red)"),
    ("gmb", "bananas"): ("01.1.6.1.2", "KG", "Bananas"),
    ("gmb", "beans"): ("01.1.7.6.1", "KG", "Beans (dry)"),
    ("gmb", "bread"): ("01.1.1.3.1", "KG", "Bread"),
    ("gmb", "cabbage"): ("01.1.7.1.2", "KG", "Cabbage"),
    ("gmb", "carrots"): ("01.1.7.4.1", "KG", "Carrots"),
    ("gmb", "cassava"): ("01.1.7.5.3", "KG", "Cassava"),
    ("gmb", "coffee_instant"): ("01.2.2.0.1", "Unit", "Coffee (instant)"),
    ("gmb", "eggs"): ("01.1.4.8.1", "Unit", "Eggs"),
    ("gmb", "fish"): ("01.1.3.1.6", "KG", "Fish (bonga)"),
    ("gmb", "garlic"): ("01.1.7.4.2", "KG", "Garlic"),
    ("gmb", "groundnuts"): ("01.1.6.8.8", "KG", "Groundnuts (shelled)"),
    ("gmb", "maize"): ("01.1.1.1.6", "KG", "Maize"),
    ("gmb", "meat_beef"): ("01.1.2.2.1", "KG", "Meat (beef)"),
    ("gmb", "meat_chicken"): ("01.1.2.2.4", "KG", "Meat (chicken)"),
    ("gmb", "meat_sheep"): ("01.1.2.2.3", "KG", "Meat (sheep)"),
    ("gmb", "milk"): ("01.1.4.1.1", "KG", "Milk"),
    ("gmb", "millet"): ("01.1.1.1.5", "KG", "Millet"),
    ("gmb", "oil"): ("01.1.5.1.9", "L", "Oil (vegetable)"),
    ("gmb", "onions"): ("01.1.7.4.3", "KG", "Onions"),
    ("gmb", "oranges"): ("01.1.6.2.3", "KG", "Oranges (big size)"),
    ("gmb", "potatoes"): ("01.1.7.5.1", "KG", "Potatoes (Irish)"),
    ("gmb", "rice"): ("01.1.1.1.2", "KG", "Rice (small grain, imported)"),
    ("gmb", "salt"): ("01.1.9.3.1", "KG", "Salt"),
    ("gmb", "sugar"): ("01.1.8.1.1", "KG", "Sugar"),
    ("gmb", "tea"): ("01.2.3.0.2", "Unit", "Tea"),
    ("gmb", "tomatoes"): ("01.1.7.2.4", "KG", "Tomatoes"),
    # --- Guinea (GIN) ----------------------------------------------
    ("gin", "beans"): ("01.1.7.6.6", "KG", "Beans (niebe, white)"),
    ("gin", "bread"): ("01.1.1.3.1", "Unit", "Bread"),
    ("gin", "cassava_meal"): ("01.1.7.9.9", "KG", "Cassava meal (gari)"),
    ("gin", "fish"): ("01.1.3.1.9", "KG", "Fish"),
    ("gin", "fonio"): ("01.1.1.1.9", "KG", "Fonio"),
    ("gin", "groundnuts"): ("01.1.6.8.8", "KG", "Groundnuts (shelled)"),
    ("gin", "maize"): ("01.1.1.1.6", "KG", "Maize"),
    ("gin", "meat_beef"): ("01.1.2.2.1", "KG", "Meat (beef)"),
    ("gin", "oil"): ("01.1.5.1.2", "L", "Oil (palm)"),
    ("gin", "onions"): ("01.1.7.4.3", "KG", "Onions (imported)"),
    ("gin", "potatoes"): ("01.1.7.5.1", "KG", "Potatoes"),
    ("gin", "rice"): ("01.1.1.1.2", "KG", "Rice (local)"),
    ("gin", "salt"): ("01.1.9.3.1", "KG", "Salt"),
    ("gin", "sugar"): ("01.1.8.1.1", "KG", "Sugar"),
    ("gin", "tomatoes"): ("01.1.7.2.4", "KG", "Tomatoes"),
    # --- Guinea-Bissau (GNB) ---------------------------------------
    ("gnb", "bananas"): ("01.1.6.1.2", "KG", "Bananas (local)"),
    ("gnb", "batteries"): ("08.1.9.2", "Unit", "Batteries (big)"),
    ("gnb", "beans"): ("01.1.7.6.1", "KG", "Beans"),
    ("gnb", "bread"): ("01.1.1.3.1", "Unit", "Bread"),
    ("gnb", "candles"): ("05.6.1.9", "Unit", "Candles (big)"),
    ("gnb", "carrots"): ("01.1.7.4.1", "KG", "Carrots"),
    ("gnb", "cassava"): ("01.1.7.5.3", "KG", "Cassava (fresh)"),
    ("gnb", "charcoal"): ("04.5.4.3", "KG", "Charcoal"),
    ("gnb", "fish"): ("01.1.3.2.9", "KG", "Fish (dry)"),
    ("gnb", "fish_barbel_sole"): ("01.1.3.1.3", "KG", "Fish (barbel, sole)"),
    ("gnb", "fish_goldstripe_sardinella"): (
        "01.1.3.1.6",
        "KG",
        "Fish (goldstripe sardinella)",
    ),
    ("gnb", "fish_mullet_catfish"): ("01.1.3.1.1", "KG", "Fish (mullet, catfish)"),
    ("gnb", "groundnuts"): ("01.1.6.8.8", "KG", "Groundnuts (shelled)"),
    ("gnb", "groundnuts_paste"): ("01.1.8.4.0", "KG", "Groundnuts (paste)"),
    ("gnb", "lemons"): ("01.1.6.2.2", "KG", "Lemons"),
    ("gnb", "maize"): ("01.1.1.1.6", "KG", "Maize"),
    ("gnb", "meat_beef"): ("01.1.2.2.1", "KG", "Meat (beef, second quality)"),
    ("gnb", "meat_chicken"): ("01.1.2.2.4", "Unit", "Meat (chicken, local)"),
    ("gnb", "milk"): ("01.1.4.3.2", "KG", "Milk (powder)"),
    ("gnb", "millet"): ("01.1.1.1.5", "KG", "Millet"),
    ("gnb", "oil"): ("01.1.5.1.2", "L", "Oil (palm)"),
    ("gnb", "okra"): ("01.1.7.2.6", "KG", "Okra (fresh)"),
    ("gnb", "onions"): ("01.1.7.4.3", "KG", "Onions"),
    ("gnb", "rice"): ("01.1.1.1.2", "KG", "Rice (imported)"),
    ("gnb", "soap"): ("13.1.2.0", "Unit", "Handwash soap"),
    ("gnb", "sorghum"): ("01.1.1.1.3", "KG", "Sorghum"),
    ("gnb", "sugar"): ("01.1.8.1.1", "KG", "Sugar"),
    ("gnb", "tomatoes"): ("01.1.7.2.4", "KG", "Tomatoes"),
    ("gnb", "wheat_flour"): ("01.1.1.2.1", "KG", "Wheat flour"),
    # --- Kenya (KEN) -----------------------------------------------
    ("ken", "beans"): ("01.1.7.6.1", "KG", "Beans (dry)"),
    ("ken", "maize_fao"): ("01.1.1.1.6", "Kg", "Maize (white)"),
    # --- Liberia (LBR) ---------------------------------------------
    ("lbr", "cowpeas"): ("01.1.7.6.6", "KG", "Cowpeas"),
    ("lbr", "oil"): ("01.1.5.1.2", "Gallon", "Oil (palm)"),
    # --- Madagascar (MDG) ------------------------------------------
    ("mdg", "rice"): ("01.1.1.1.2", "KG", "Rice (local)"),
    ("mdg", "sugar"): ("01.1.8.1.1", "KG", "Sugar"),
    ("mdg", "wheat_flour"): ("01.1.1.2.1", "KG", "Wheat flour"),
    # --- Malawi (MWI) ----------------------------------------------
    ("mwi", "beans"): ("01.1.7.6.1", "KG", "Beans"),
    ("mwi", "cassava"): ("01.1.7.5.3", "KG", "Cassava"),
    ("mwi", "groundnuts"): ("01.1.6.8.8", "KG", "Groundnuts (shelled)"),
    ("mwi", "maize"): ("01.1.1.1.6", "KG", "Maize"),
    ("mwi", "rice"): ("01.1.1.1.2", "KG", "Rice"),
    # --- Mali (MLI) ------------------------------------------------
    ("mli", "beans"): ("01.1.7.6.6", "KG", "Beans (niebe)"),
    ("mli", "groundnuts"): ("01.1.6.8.8", "KG", "Groundnuts (shelled)"),
    ("mli", "maize"): ("01.1.1.1.6", "KG", "Maize"),
    ("mli", "millet"): ("01.1.1.1.5", "KG", "Millet"),
    ("mli", "rice"): ("01.1.1.1.2", "KG", "Rice (local)"),
    ("mli", "sorghum"): ("01.1.1.1.3", "KG", "Sorghum"),
    # --- Mauritania (MRT) ------------------------------------------
    ("mrt", "couscous_fao"): ("01.1.1.5.0", "Kg", "Couscous"),
    ("mrt", "meat_beef_fao"): ("01.1.2.2.1", "Kg", "Meat (Beef)"),
    ("mrt", "meat_camel_fao"): ("01.1.2.2.7", "Kg", "Meat (Camel)"),
    ("mrt", "milk"): ("01.1.4.3.2", "KG", "Milk (powder)"),
    ("mrt", "oil"): ("01.1.5.1.9", "L", "Oil (vegetable)"),
    ("mrt", "rice"): ("01.1.1.1.2", "KG", "Rice (imported)"),
    ("mrt", "sorghum"): ("01.1.1.1.3", "KG", "Sorghum (taghalit)"),
    ("mrt", "sugar"): ("01.1.8.1.1", "KG", "Sugar"),
    ("mrt", "wheat"): ("01.1.1.1.1", "KG", "Wheat"),
    ("mrt", "wheat_flour"): ("01.1.1.2.1", "KG", "Wheat flour"),
    # --- Mozambique (MOZ) ------------------------------------------
    ("moz", "cowpeas"): ("01.1.7.6.6", "KG", "Cowpeas"),
    ("moz", "cowpeased_fao"): ("01.1.7.6.6", "Kg", "Cowpeas (mixed)"),
    ("moz", "groundnuts"): ("01.1.6.8.8", "KG", "Groundnuts (small, shelled)"),
    ("moz", "maize"): ("01.1.1.1.6", "KG", "Maize (white)"),
    ("moz", "maize_meal"): ("01.1.1.2.6", "KG", "Maize meal (white, first grade)"),
    ("moz", "oil"): ("01.1.5.1.9", "L", "Oil (vegetable, local)"),
    ("moz", "rice"): ("01.1.1.1.2", "KG", "Rice (imported)"),
    ("moz", "sugar"): ("01.1.8.1.1", "KG", "Sugar (brown, local)"),
    ("moz", "wheat_flour"): ("01.1.1.2.1", "KG", "Wheat flour (local)"),
    # --- Niger (NER) -----------------------------------------------
    ("ner", "beans"): ("01.1.7.6.6", "KG", "Beans (niebe)"),
    ("ner", "maize"): ("01.1.1.1.6", "KG", "Maize"),
    ("ner", "millet"): ("01.1.1.1.5", "KG", "Millet"),
    ("ner", "rice"): ("01.1.1.1.2", "KG", "Rice (imported)"),
    ("ner", "sorghum"): ("01.1.1.1.3", "KG", "Sorghum"),
    # --- Nigeria (NGA) ---------------------------------------------
    ("nga", "beans"): ("01.1.7.6.1", "2.5 KG", "Beans (red)"),
    ("nga", "eggs"): ("01.1.4.8.1", "30 pcs", "Eggs"),
    ("nga", "fish"): ("01.1.3.1.9", "KG", "Fish"),
    ("nga", "gari_fao"): ("01.1.7.9.9", "Kg", "Gari (white)"),
    ("nga", "groundnuts"): ("01.1.6.8.8", "2.2 KG", "Groundnuts"),
    ("nga", "maize_fao"): ("01.1.1.1.6", "Kg", "Maize (white)"),
    ("nga", "maize_flour"): ("01.1.1.2.6", "2.1 KG", "Maize flour"),
    ("nga", "meat_beef"): ("01.1.2.2.1", "KG", "Meat (beef)"),
    ("nga", "meat_goat"): ("01.1.2.2.3", "KG", "Meat (goat)"),
    ("nga", "milk"): ("01.1.4.3.2", "400 G", "Milk (powder)"),
    ("nga", "millet"): ("01.1.1.1.5", "2.6 KG", "Millet"),
    ("nga", "onions"): ("01.1.7.4.3", "0.5 KG", "Onions"),
    ("nga", "rice"): ("01.1.1.1.2", "2.8 KG", "Rice (imported)"),
    ("nga", "sorghum_fao"): ("01.1.1.1.3", "Kg", "Sorghum (white)"),
    ("nga", "yam"): ("01.1.7.5.4", "2.5 KG", "Yam"),
    # --- Senegal (SEN) ---------------------------------------------
    ("sen", "maize"): ("01.1.1.1.6", "KG", "Maize (local)"),
    ("sen", "millet"): ("01.1.1.1.5", "KG", "Millet"),
    ("sen", "rice"): ("01.1.1.1.2", "KG", "Rice (imported)"),
    ("sen", "sorghum"): ("01.1.1.1.3", "KG", "Sorghum"),
    # --- Somalia (SOM) ---------------------------------------------
    ("som", "maize"): ("01.1.1.1.6", "KG", "Maize (white)"),
    ("som", "milk"): ("01.1.4.1.4", "L", "Milk (camel)"),
    ("som", "oil"): ("01.1.5.1.9", "L", "Oil (vegetable, imported)"),
    ("som", "rice"): ("01.1.1.1.2", "KG", "Rice (imported)"),
    ("som", "sorghum"): ("01.1.1.1.3", "KG", "Sorghum (red)"),
    ("som", "wheat_fao"): ("01.1.1.1.1", "Kg", "Wheat"),
    ("som", "wheat_flour_fao"): ("01.1.1.2.1", "Kg", "Wheat (flour)"),
    # --- South Sudan (SSD) -----------------------------------------
    ("ssd", "beans"): ("01.1.7.6.1", "KG", "Beans (red)"),
    ("ssd", "cassava"): ("01.1.7.7.0", "3.5 KG", "Cassava (dry)"),
    ("ssd", "groundnuts"): ("01.1.6.8.8", "KG", "Groundnuts (shelled)"),
    ("ssd", "maize"): ("01.1.1.1.6", "3.5 KG", "Maize (white)"),
    ("ssd", "maize_meal"): ("01.1.1.2.6", "KG", "Maize meal"),
    ("ssd", "millet"): ("01.1.1.1.5", "3.5 KG", "Millet (white)"),
    ("ssd", "oil"): ("01.1.5.1.9", "L", "Oil (vegetable)"),
    ("ssd", "rice"): ("01.1.1.1.2", "KG", "Rice"),
    ("ssd", "salt"): ("01.1.9.3.1", "KG", "Salt"),
    ("ssd", "sesame"): ("01.1.9.4.0", "3.5 KG", "Sesame"),
    ("ssd", "sorghum"): ("01.1.1.1.3", "3.5 KG", "Sorghum (white, imported)"),
    ("ssd", "sugar"): ("01.1.8.1.1", "KG", "Sugar (brown, imported)"),
    ("ssd", "wheat_flour"): ("01.1.1.2.1", "KG", "Wheat flour"),
    # --- Sudan (SDN) -----------------------------------------------
    ("sdn", "meat_beef"): ("01.1.2.2.1", "KG", "Meat (beef)"),
    ("sdn", "milk"): ("01.1.4.3.2", "KG", "Milk (powder)"),
    ("sdn", "millet"): ("01.1.1.1.5", "3.5 KG", "Millet"),
    ("sdn", "oil"): ("01.1.5.1.9", "L", "Oil (vegetable)"),
    ("sdn", "onions"): ("01.1.7.4.3", "KG", "Onions"),
    ("sdn", "sorghum"): ("01.1.1.1.3", "3 KG", "Sorghum"),
    ("sdn", "sorghum_food_aid"): ("01.1.1.1.3", "3 KG", "Sorghum (food aid)"),
    ("sdn", "sugar"): ("01.1.8.1.1", "KG", "Sugar"),
    ("sdn", "tomatoes"): ("01.1.7.7.0", "KG", "Tomatoes (dried)"),
    # --- Uganda (UGA) ----------------------------------------------
    ("uga", "beans"): ("01.1.7.6.1", "KG", "Beans"),
    ("uga", "cassava_flour"): ("01.1.7.9.1", "KG", "Cassava flour"),
    ("uga", "maize"): ("01.1.1.1.6", "KG", "Maize (white)"),
    ("uga", "maize_flour"): ("01.1.1.2.6", "KG", "Maize flour"),
    ("uga", "millet"): ("01.1.1.1.5", "KG", "Millet"),
    ("uga", "oil"): ("01.1.5.1.9", "L", "Oil (vegetable)"),
    ("uga", "salt"): ("01.1.9.3.1", "KG", "Salt"),
    ("uga", "sorghum"): ("01.1.1.1.3", "KG", "Sorghum"),
}

# Parsed global panel, kept for the life of the process. See the module
# docstring: one download serves 37 countries.
_GLOBAL_FRAME: pd.DataFrame | None = None


def _resolve_zip_url(session, catalog_id: int) -> str | None:
    """Return the newest market-panel zip URL for a study, accepting terms first.

    Two things make this fiddlier than it looks. The download links only render
    after a click-through POST carrying a CSRF token. And a study exposes EVERY
    weekly vintage at once -- 317 resource ids for Lao PDR alone -- so the newest
    has to be picked deliberately rather than by taking whatever comes first.

    The filename lives in `content-disposition`, not in the page: every link's
    visible text is just the URL again. So candidates are probed with HEAD, in
    page order, which puts the newest vintage first.

    The match must be `_RTFP_mkt_`, not `_mkt_`. Each vintage ships three files
    whose names all contain `_mkt_`, and the two decoys -- `_RTP_details_mkt_`
    and `_RTP_ticker_info_mkt_` -- are listed BEFORE the data file and are a few
    hundred bytes each.
    """
    page = f"{_BASE}/index.php/catalog/{catalog_id}/get-microdata"
    try:
        got = session.get(page, timeout=90)
        got.raise_for_status()
        token = re.search(r'name="ncsrf"[^>]*value="([0-9a-fA-F]+)"', got.text)
        html = got.text
        if token:
            posted = session.post(
                page, data={"ncsrf": token.group(1), "accept": "Accept"}, timeout=90
            )
            posted.raise_for_status()
            html = posted.text
    except Exception as exc:  # noqa: BLE001 — network or markup change
        logger.warning("[wb_rtdi] terms acceptance failed for %s: %s", catalog_id, exc)
        return None

    seen: list[str] = []
    for rid in re.findall(rf"catalog/{catalog_id}/download/(\d+)", html):
        if rid not in seen:
            seen.append(rid)
    if not seen:
        logger.warning("[wb_rtdi] no download links for catalog %s", catalog_id)
        return None

    for rid in seen[:_MAX_PROBES]:
        url = f"{_BASE}/index.php/catalog/{catalog_id}/download/{rid}"
        try:
            head = session.head(url, timeout=60, allow_redirects=True)
            name = re.search(
                r"filename\*?=(?:UTF-8'')?\"?([^\";]+)",
                head.headers.get("content-disposition", ""),
            )
        except Exception:  # noqa: BLE001 — probe failure is not fatal
            continue
        if name and "_RTFP_mkt_" in name.group(1) and name.group(1).endswith(".zip"):
            logger.info("[wb_rtdi] catalog %s -> %s", catalog_id, name.group(1).strip())
            return url
    logger.warning(
        "[wb_rtdi] no _RTFP_mkt_ zip in the first %d of %d resources for catalog %s",
        _MAX_PROBES,
        len(seen),
        catalog_id,
    )
    return None


def _wanted(column: str) -> bool:
    """Column filter for the panel CSVs.

    The global panel has 725 columns and 737k rows; read whole it costs several
    GB for data that is 90% unmapped tickers and OHLC legs we never use. Only the
    identity columns and the `c_<ticker>` close series of mapped tickers are kept.
    """
    if column in {"ISO3", "country", "mkt_name", "DATES", "price_date", "currency"}:
        return True
    return column.startswith("c_") and column[2:] in {t for _, t in _ITEMS}


def _market_frame(blob: bytes) -> pd.DataFrame | None:
    """Extract the market-level CSV from a study zip.

    Read in chunks. The global panel is ~1.1 GB of CSV across 725 columns, and
    handing that to `read_csv` in one call peaks above 10 GB of resident memory
    -- the parser holds the whole tokenized block before `usecols` narrows it.
    Chunking caps the transient cost at one block, which matters because this
    runs inside `collect` alongside everything else.
    """
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        names = [
            n
            for n in zf.namelist()
            if n.lower().endswith(".csv")
            and "_mkt_" in n
            and "details" not in n.lower()
            and "ticker" not in n.lower()
        ]
        if not names:
            return None
        with zf.open(names[0]) as fh:
            chunks = pd.read_csv(fh, usecols=_wanted, chunksize=50_000)
            return pd.concat(chunks, ignore_index=True)


def _download_panel(catalog_id: int) -> pd.DataFrame | None:
    session = get_session()
    url = _resolve_zip_url(session, catalog_id)
    if not url:
        return None
    try:
        resp = session.get(url, timeout=900)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[wb_rtdi] zip fetch failed for catalog %s: %s", catalog_id, exc)
        return None
    frame = _market_frame(resp.content)
    if frame is None or frame.empty:
        logger.warning("[wb_rtdi] no market CSV inside catalog %s", catalog_id)
        return None
    return frame


def _load_global() -> pd.DataFrame | None:
    global _GLOBAL_FRAME
    if _GLOBAL_FRAME is None:
        logger.info(
            "[wb_rtdi] downloading the global panel (catalog %s)", _GLOBAL_CATALOG
        )
        _GLOBAL_FRAME = _download_panel(_GLOBAL_CATALOG)
        if _GLOBAL_FRAME is not None:
            logger.info(
                "[wb_rtdi] global panel: %d market-months, %d countries",
                len(_GLOBAL_FRAME),
                _GLOBAL_FRAME["ISO3"].nunique(),
            )
    return _GLOBAL_FRAME


def _rows(
    df: pd.DataFrame, iso3: str, country: str, url: str, cutoff: date
) -> list[dict]:
    source_key = f"wb_rtdi_{iso3}"
    ts = get_scrape_ts()
    # The global panel names its date column DATES; the standalone country
    # studies name the same column price_date.
    date_col = "DATES" if "DATES" in df.columns else "price_date"
    dates = pd.to_datetime(df[date_col], errors="coerce")
    keep = dates.notna() & (dates.dt.date >= cutoff)
    df, dates = df[keep], dates[keep]
    if df.empty:
        return []
    currency = (
        str(df["currency"].dropna().iloc[0]) if len(df["currency"].dropna()) else None
    )

    out: list[dict] = []
    for (i3, ticker), (code, unit_raw, full_name) in _ITEMS.items():
        if i3 != iso3:
            continue
        col = f"c_{ticker}"
        if col not in df.columns:
            logger.warning(
                "[%s] declared ticker %s absent from panel", source_key, ticker
            )
            continue
        price = pd.to_numeric(df[col], errors="coerce")
        ok = price.notna() & (price > 0)
        if not ok.any():
            continue
        sub = df[ok]
        for obs_date, market, value in zip(
            dates[ok].dt.date, sub.get("mkt_name", pd.Series(dtype=str)), price[ok]
        ):
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "monthly",
                "country": country,
                "subnational_area": str(market) if pd.notna(market) else None,
                "source_key": source_key,
                # Curated per item -- see the module docstring.
                "coicop_code": code,
                "item_name": full_name,
                "price_local": round(float(value), 4),
                "currency": currency,
                "unit": unit_raw,
                "source_url": url,
                "notes": f"WB RTDI monthly close; ticker={ticker}; market-level estimate",
                "scrape_ts": ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            out.append(row)
    return out


def _fetch(cutoff: date, *, iso3: str) -> pd.DataFrame | None:
    country, catalog_id = _COUNTRIES[iso3]
    source_key = f"wb_rtdi_{iso3}"
    if catalog_id is None:
        frame = _load_global()
        if frame is None:
            return None
        frame = frame[frame["ISO3"].str.upper() == iso3.upper()]
        catalog_id = _GLOBAL_CATALOG
        if frame.empty:
            logger.warning("[%s] absent from the global panel", source_key)
            return None
    else:
        frame = _download_panel(catalog_id)
        if frame is None:
            return None
    rows = _rows(
        frame, iso3, country, f"{_BASE}/index.php/catalog/{catalog_id}", cutoff
    )
    logger.info("[%s] %d market-month rows (cutoff=%s)", source_key, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None


def fetch_wb_rtdi_idn(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="idn")


def fetch_wb_rtdi_lao(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="lao")


def fetch_wb_rtdi_mmr(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="mmr")


def fetch_wb_rtdi_phl(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="phl")


def fetch_wb_rtdi_arm(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="arm")


def fetch_wb_rtdi_gtm(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="gtm")


def fetch_wb_rtdi_hti(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="hti")


def fetch_wb_rtdi_afg(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="afg")


def fetch_wb_rtdi_irq(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="irq")


def fetch_wb_rtdi_lbn(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="lbn")


def fetch_wb_rtdi_lby(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="lby")


def fetch_wb_rtdi_syr(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="syr")


def fetch_wb_rtdi_yem(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="yem")


def fetch_wb_rtdi_bgd(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="bgd")


def fetch_wb_rtdi_lka(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="lka")


def fetch_wb_rtdi_bfa(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="bfa")


def fetch_wb_rtdi_bdi(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="bdi")


def fetch_wb_rtdi_cmr(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="cmr")


def fetch_wb_rtdi_caf(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="caf")


def fetch_wb_rtdi_tcd(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="tcd")


def fetch_wb_rtdi_cod(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="cod")


def fetch_wb_rtdi_cog(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="cog")


def fetch_wb_rtdi_eth(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="eth")


def fetch_wb_rtdi_gmb(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="gmb")


def fetch_wb_rtdi_gin(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="gin")


def fetch_wb_rtdi_gnb(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="gnb")


def fetch_wb_rtdi_ken(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="ken")


def fetch_wb_rtdi_lbr(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="lbr")


def fetch_wb_rtdi_mdg(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="mdg")


def fetch_wb_rtdi_mwi(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="mwi")


def fetch_wb_rtdi_mli(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="mli")


def fetch_wb_rtdi_mrt(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="mrt")


def fetch_wb_rtdi_moz(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="moz")


def fetch_wb_rtdi_ner(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="ner")


def fetch_wb_rtdi_nga(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="nga")


def fetch_wb_rtdi_sen(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="sen")


def fetch_wb_rtdi_som(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="som")


def fetch_wb_rtdi_ssd(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="ssd")


def fetch_wb_rtdi_sdn(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="sdn")


def fetch_wb_rtdi_uga(cutoff: date) -> pd.DataFrame | None:
    return _fetch(cutoff, iso3="uga")
