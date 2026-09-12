"""HARTI Sri Lanka -- daily wholesale food price bulletins.

The Hector Kobbekaduwa Agrarian Research and Training Institute (HARTI, a
statutory institute under the Ministry of Agriculture) publishes one PDF per
trading day carrying two tables:

  1. "(Wholesale Prices of Rice & Subsidiary Food Crops)" -- rice grades,
     dried chillies, onions, potatoes, pulses, sugar, wheat flour and eggs at
     the Pettah and Marandagahamula wholesale markets, as a low-high range
     plus the market AVERAGE (which is what this fetcher emits).
  2. "Wholesale Prices in Selected Markets" -- vegetables and (in later
     issues) fruit at up to ten dedicated wholesale markets, as a low-high
     range only; the midpoint is emitted.

Every issue also repeats table 2 in Sinhala. Those pages are ignored: in the
older bulletins the Sinhala text layer is a legacy non-Unicode font that
extracts as mojibake, and the numbers are the same ones the English page
already carries.

DISCOVERY / DATING
------------------
`/daily-price.php` lists every bulletin in an HTML table whose FIRST COLUMN is
the ISO date. The observation date is taken from that column, never from the
PDF, because the filenames are inconsistent (`daily_31-12-2015.pdf`,
`Vegetable Pricenew ex1(2026.09.10).pdf`, `Vegetables Wholesale Prices
(2026.09.09)1.pdf`, `Vegetabale Wholesale Prices (...)` -- with a typo) and
some rows carry no filename convention at all. Measured 2026-09-11: 3,089
bulletins, 2015-06-22 to 2026-09-10, all English.

Hrefs are site-relative and contain spaces and parentheses, so each one is
percent-encoded before the request.

PARSING -- WHY WORD POSITIONS AND NOT `extract_tables`
------------------------------------------------------
Neither table is ruled. `extract_tables()` returns one merged mega-cell
containing every item name joined by newlines, and `extract_text()` flows the
columns together in a way that cannot be split reliably: the "Change" column
is OMITTED when a price did not move, so a text line has a variable number of
numbers and no way to tell which market a trailing number belongs to.

Both parsers therefore work from `extract_words()` x-coordinates and take
their column anchors from the document's own header row:

  * table 2 -- the row of repeated "Market" words under the market names.
    Column boundaries are the midpoints between adjacent anchor centres, which
    is what makes the parser indifferent to the market count. That count grows
    over the archive: SIX markets in 2015, eight in 2018, nine in 2021, ten in
    2026.
  * table 1 -- the two "Average" words in the "Range | Average | Change *"
    header, matched back to the market names ("Pettah", "Marandagahamula") on
    the line above.

NAME-ONLY LINES ARE AMBIGUOUS, AND THE AMBIGUITY IS RESOLVED BY LOOKAHEAD.
A line carrying a name and no numbers is either a section header ("Rice (Rs/50
kg)", "Imported Rice", "Pulses (Rs/Kg)") or an item whose numbers wrapped onto
the next line ("Welimada", "Cowpea"). The parser holds such a line pending: if
the next data line brings its own name, the pending line was a header; if it
brings none, the pending line was the item. Guessing from indentation was
tried and is not stable across the archive.

THE 50x TRAP
------------
The rice table's unit is published in its own section header and IT CHANGED.
Bulletins up to roughly 2020 read "Rice (Rs/50 kg)" and quote a 50 kg bag
(Samba 1 at 4,830 on 2015-12-31); later bulletins read "Rice (Rs/kg)" (Samba 1
at 228.60 on 2026-09-10). The parser reads the unit out of each section header
and emits it, so the two eras are not silently merged into one 50x-inconsistent
series. `unit` is one of "50 kg", "kg" or "Egg" exactly as published.

COICOP
------
`_COICOP_MAP` is keyed on the normalised item label -- for table 1 that is
"<section> - <row>", because the row labels there are not unique on their own
("Imported" appears under Dried Chillies, Big Onion AND Potatoes). Unmapped
labels are logged and DROPPED.

`coicop_classification: classifier` with a per-row `coicop_code` is deliberate
and matches zm_mfl_market_bulletin: concatenate._build_classifier_csv_map
ingests a fetcher CSV only for `classifier` sources, so `source_curated` would
delete this source's rows from the build. The per-row code rides through as
declared_coicop_codes and short-circuits classify at confidence 1.0.

Emits PriceObservation rows.
"""

from __future__ import annotations

import io
import logging
import re
import urllib.parse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_BASE = "https://www.harti.gov.lk/"
_INDEX_URL = _BASE + "daily-price.php"
_COUNTRY = "Sri Lanka"
_CURRENCY = "LKR"
_SOURCE_KEY = "lk_harti_daily_prices"

_IDENT = ["source_key", "observation_date", "subnational_area", "item_name"]

_NUM = re.compile(r"^\d+(?:\.\d+)?$")
_RANGE = re.compile(r"^(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)$")
_UNIT_RE = re.compile(r"\(\s*Rs\s*[./]\s*([^)]+?)\s*\)", re.I)
_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")

_WORKERS = 8

def _norm(s: object) -> str:
    t = str(s or "").replace("’", "'").replace("\xa0", " ")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _key(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", label.lower())


# Unit-less section headings of the rice / subsidiary table. Every other
# heading carries its unit ("Rice (Rs/50 kg)", "Pulses (Rs/Kg)") and is
# recognised by that; these four do not.
_RICE_SECTIONS = {
    _key(s)
    for s in (
        "Imported Rice",
        "Local Rice",
        "Big Onion",
        "Kora",
        "Subsidiary Food Crops",
        "Other Field Crops",
    )
}

_MARKET_ALIASES = {
    "petha": "Pettah",
    "pettah": "Pettah",
    "peliyagoda": "Peliyagoda",
    "kandy": "Kandy",
    "dambulla": "Dambulla",
    "meegoda": "Meegoda",
    "megoda": "Meegoda",
    "norochchole": "Norochchole",
    "thambuththegama": "Thambuththegama",
    "thambuththegam": "Thambuththegama",
    "tthegama": "Thambuththegama",
    "keppetipola": "Keppetipola",
    "kappetipola": "Keppetipola",
    "nuwaraeliya": "Nuwaraeliya",
    "bandarawela": "Bandarawela",
    "veyangoda": "Veyangoda",
    "marandagahamula": "Marandagahamula",
}

# Normalised label -> (item_name, COICOP-2018 leaf).
#
# Table-1 labels are "<section> - <row>" because the row labels there are not
# unique on their own: "Imported" appears under Dried Chillies, Big Onion AND
# Potatoes. A handful of issues fail to render the "Rice (Rs/kg)" section
# header, so the bare rice grades are mapped too.
#
# Potatoes and big onion are priced in BOTH tables, at Pettah in both, so the
# two tables' item names are deliberately kept distinct ("(wholesale)" vs
# "(selected markets)"). Without that the two rows would collide on
# observation_hash and one would be silently dropped.
_RICE_ITEMS = {
    "Rice - Samba 1": "Rice, Samba 1",
    "Rice - Samba 2": "Rice, Samba 2",
    "Rice - Samba 3": "Rice, Samba 3",
    "Rice - Keeri Samba": "Rice, Keeri Samba",
    "Rice - Nadu 1": "Rice, Nadu 1",
    "Rice - Nadu 2": "Rice, Nadu 2",
    "Rice - Raw red": "Rice, raw red",
    "Rice - Raw White": "Rice, raw white",
    "Samba 1": "Rice, Samba 1",
    "Samba 2": "Rice, Samba 2",
    "Keeri Samba": "Rice, Keeri Samba",
    "Nadu 1": "Rice, Nadu 1",
    "Nadu 2": "Rice, Nadu 2",
    "Raw red": "Rice, raw red",
    "Raw White": "Rice, raw white",
    "Kora - Raw White": "Rice, Kora raw white",
    "Kora - Nadu": "Rice, Kora Nadu",
    "Imported Rice - Ponne Samba": "Rice, imported Ponne Samba",
    "Imported Rice - Samba Ponne 1": "Rice, imported Samba Ponne 1",
    "Imported Rice - Ponne 1": "Rice, imported Ponne 1",
    "Imported Rice - Nadu": "Rice, imported Nadu",
    "Imported Rice - Raw White": "Rice, imported raw white",
    "Imported Rice - Raw red": "Rice, imported raw red",
}

_COICOP_MAP: dict[str, tuple[str, str]] = {}
for _label, _item in _RICE_ITEMS.items():
    _COICOP_MAP[_key(_label)] = (f"{_item} (wholesale)", "01.1.1.1.2")

for _label, _item, _code in [
    # -- table 1: subsidiary food crops -------------------------------
    ("Dried Chillies - Imported", "Dried chillies, imported", "01.1.9.4.0"),
    ("Dried Chillies - Local", "Dried chillies, local", "01.1.9.4.0"),
    ("Onion - Sinnan", "Red onion, Sinnan", "01.1.7.4.3"),
    ("Onion - Vedalan", "Red onion, Vedalan", "01.1.7.4.3"),
    ("Onion - Imported", "Red onion, imported", "01.1.7.4.3"),
    ("Big Onion - Imported", "Big onion, imported", "01.1.7.4.3"),
    ("Big Onion - Local", "Big onion, local", "01.1.7.4.3"),
    ("Potatoes - Welimada", "Potatoes, Welimada", "01.1.7.5.1"),
    ("Potatoes - Nuwaraeliya", "Potatoes, Nuwara Eliya", "01.1.7.5.1"),
    ("Potatoes - Imported", "Potatoes, imported", "01.1.7.5.1"),
    ("Pulses - Green Gram", "Green gram, dried", "01.1.7.6.1"),
    ("Pulses - Black Gram", "Black gram, dried", "01.1.7.6.1"),
    ("Pulses - Cowpea", "Cowpea, dried", "01.1.7.6.6"),
    ("Pulses - Cowpea (White)", "Cowpea, white, dried", "01.1.7.6.6"),
    ("Pulses - Red Dhal", "Red lentils (dhal)", "01.1.7.6.4"),
    ("Consumption Item - Sugar(White)", "Sugar, white", "01.1.8.1.1"),
    ("Consumption Item - Wheat Flour", "Wheat flour", "01.1.1.2.1"),
    ("Eggs - Brown", "Eggs, brown", "01.1.4.8.1"),
    ("Eggs - White", "Eggs, white", "01.1.4.8.1"),
]:
    _COICOP_MAP[_key(_label)] = (f"{_item} (wholesale)", _code)

for _label, _item, _code in [
    # -- table 2: vegetables ------------------------------------------
    ("Beans", "Green beans", "01.1.7.3.2"),
    ("Long Beans", "Long beans", "01.1.7.3.2"),
    ("Carrot", "Carrot", "01.1.7.4.1"),
    ("Leeks", "Leeks", "01.1.7.4.4"),
    ("Beet root", "Beetroot", "01.1.7.4.9"),
    ("Beet root (N Eliya)", "Beetroot, Nuwara Eliya", "01.1.7.4.9"),
    ("Beet Root(N'Eliya)", "Beetroot, Nuwara Eliya", "01.1.7.4.9"),
    ("Knolkhol", "Knol khol (kohlrabi)", "01.1.7.1.9"),
    ("Raddish", "Radish", "01.1.7.4.9"),
    ("Cabbage (N'Eliya)", "Cabbage, Nuwara Eliya", "01.1.7.1.2"),
    ("Cabbage (Kandy)", "Cabbage, Kandy", "01.1.7.1.2"),
    ("Tomato", "Tomato", "01.1.7.2.4"),
    ("Ladies Fingers", "Okra (ladies fingers)", "01.1.7.2.6"),
    ("Brinjals", "Brinjal (aubergine)", "01.1.7.2.3"),
    ("Brinjals (Other)", "Brinjal, other", "01.1.7.2.3"),
    ("Brinjals (Village)", "Brinjal, village", "01.1.7.2.3"),
    ("Eggplant", "Eggplant", "01.1.7.2.3"),
    ("Capsicum", "Capsicum", "01.1.7.2.1"),
    ("Green Chillies", "Green chillies", "01.1.7.2.1"),
    ("Pumpkin", "Pumpkin", "01.1.7.2.5"),
    ("Snake Gourd", "Snake gourd", "01.1.7.2.5"),
    ("Luffa", "Luffa (ridge gourd)", "01.1.7.2.5"),
    ("Bitter Gourd", "Bitter gourd", "01.1.7.2.5"),
    ("Bitter Gourd (Other)", "Bitter gourd, other", "01.1.7.2.5"),
    ("Bitter Gourd (Village)", "Bitter gourd, village", "01.1.7.2.5"),
    ("Cucumber", "Cucumber", "01.1.7.2.2"),
    ("Drumstick", "Drumstick (moringa pod)", "01.1.7.2.9"),
    ("Ash Plantains", "Ash plantain (cooking banana)", "01.1.7.5.7"),
    ("Manioc", "Manioc (cassava)", "01.1.7.5.3"),
    ("Sweet Potatoe", "Sweet potato", "01.1.7.5.2"),
    ("Sweet Potato", "Sweet potato", "01.1.7.5.2"),
    ("Potato (Nuwaraeliya)", "Potatoes, Nuwara Eliya", "01.1.7.5.1"),
    ("Potato (Welimada)", "Potatoes, Welimada", "01.1.7.5.1"),
    ("Potato(Imported)", "Potatoes, imported", "01.1.7.5.1"),
    ("B'Onion Imported", "Big onion, imported", "01.1.7.4.3"),
    ("B'Onion(Imported)", "Big onion, imported", "01.1.7.4.3"),
    ("Big-onion Local", "Big onion, local", "01.1.7.4.3"),
    ("Soya", "Soya bean", "01.1.7.6.9"),
    ("Black Gram", "Black gram, dried", "01.1.7.6.1"),
    # -- table 2: fruit ------------------------------------------------
    ("Lime", "Lime", "01.1.6.2.2"),
    ("Orange", "Orange", "01.1.6.2.3"),
    ("Avocado", "Avocado", "01.1.6.1.1"),
    ("Papaya", "Papaya", "01.1.6.1.6"),
    ("Pineapple - Large", "Pineapple, large", "01.1.6.1.7"),
    ("Pineapple - Medium", "Pineapple, medium", "01.1.6.1.7"),
    ("Pineapple - Small", "Pineapple, small", "01.1.6.1.7"),
    ("Banana", "Banana", "01.1.6.1.2"),
    ("Seeni", "Banana, Seeni", "01.1.6.1.2"),
    ("Ambul", "Banana, Ambul", "01.1.6.1.2"),
    ("Anamalu", "Banana, Anamalu", "01.1.6.1.2"),
    ("Kolikuttu", "Banana, Kolikuttu", "01.1.6.1.2"),
    ("Mango - Betti", "Mango, Betti", "01.1.6.1.5"),
    ("Mango - Karathakolomban", "Mango, Karuthakolomban", "01.1.6.1.5"),
    ("Mango - Karathakolom", "Mango, Karuthakolomban", "01.1.6.1.5"),
    ("Pineapple - Large - Karathakolom", "Mango, Karuthakolomban", "01.1.6.1.5"),
    ("Woodapple", "Wood apple", "01.1.6.1.9"),
    ("Passion Fruits", "Passion fruit", "01.1.6.1.9"),
]:
    _COICOP_MAP[_key(_label)] = (f"{_item} (selected markets)", _code)



def _canon_unit(unit: str) -> str:
    """The publisher writes the same unit several ways across the archive
    ("Kg" / "kg", "Fruit" / "Fruits"). Casing is normalised so downstream
    grouping does not split one series in two; "50 kg" is kept distinct from
    "kg" because it really is a different quantity."""
    u = _norm(unit).lower()
    if u in {"fruits", "fruit"}:
        return "fruit"
    if u == "egg":
        return "egg"
    return u


def _lines(page) -> list[list[dict]]:
    rows: dict[int, list[dict]] = defaultdict(list)
    for w in page.extract_words():
        rows[round(w["top"] / 3)].append(w)
    return [sorted(rows[k], key=lambda w: w["x0"]) for k in sorted(rows)]


def _centre(w: dict) -> float:
    return (w["x0"] + w["x1"]) / 2.0


def _split(line: list[dict], left: float) -> tuple[str, list[dict]]:
    name = _norm(" ".join(w["text"] for w in line if w["x1"] <= left))
    data = [w for w in line if w["x1"] > left]
    return name, data


def _market_name(raw: str) -> str:
    return _MARKET_ALIASES.get(_key(raw), _norm(raw))


def _strip_unit(name: str) -> tuple[str, str | None]:
    """Split an inline unit off an item label: 'Papaya (Rs/Kg)' -> ('Papaya',
    'Kg'). Some issues print the unit against the ITEM rather than against the
    section header, and the fruit rows are where it matters -- 'Anamalu
    (Rs/Fruits)' is a per-fruit price sitting in a per-kg table."""
    m = _UNIT_RE.search(name)
    if not m:
        return name, None
    return _norm(_UNIT_RE.sub("", name)), _norm(m.group(1))


def _name_columns(name_line, anchors, column) -> list[str]:
    """Market names, one per anchor column.

    The names are NOT simply the words of the header line: pdfplumber merges
    adjacent header cells into a single word in several eras of this archive
    ("NorochcholeThambuththegamaKappetipola" in the 2021 issues). A merged word
    spans more than one anchor, so it is split back on its internal capital
    letters and the pieces are handed out in order; if the piece count does not
    match the span, every covered column gets the whole string rather than a
    guess."""
    names = [""] * len(anchors)
    centres = [_centre(a) for a in anchors]
    for w in name_line:
        covered = [i for i, c in enumerate(centres) if w["x0"] <= c <= w["x1"]]
        if len(covered) > 1:
            pieces = re.split(r"(?<=[a-z'.])(?=[A-Z])", w["text"])
            if len(pieces) == len(covered):
                for i, piece in zip(covered, pieces):
                    names[i] = piece
            else:
                for i in covered:
                    names[i] = w["text"]
            continue
        k = column(w)
        if 0 <= k < len(names) and not names[k]:
            names[k] = w["text"]
    return [_market_name(n) if n else "" for n in names]


def parse_market_page(page) -> list[tuple[str, str, str, float]]:
    """[(variety, market, unit, price)] from 'Wholesale Prices in Selected
    Markets'. Price is the midpoint of the published low-high range; a lone
    number is taken as-is."""
    lines = _lines(page)
    anchors = None
    name_line = None
    start = 0
    for i, line in enumerate(lines):
        texts = [w["text"] for w in line]
        if not texts or not texts[0].lower().startswith("variety"):
            continue
        for j in (i + 1, i + 2):
            if j < len(lines) and sum(1 for w in lines[j] if w["text"] == "Market") >= 3:
                anchors = [w for w in lines[j] if w["text"] == "Market"]
                # The market names sit on the "Variety" line itself in most
                # issues, but the 2024 issues break "Variety" onto its own line
                # and put the names on the next one, with the "Market" anchors
                # a line further down. Reading them off the wrong line is what
                # produced "column 1".."column 10" for a whole year.
                name_line = line[1:] if j == i + 1 else lines[j - 1]
                start = j + 1
                break
        if anchors:
            break
    if not anchors:
        return []

    centres = [_centre(w) for w in anchors]
    bounds = [(centres[k] + centres[k + 1]) / 2 for k in range(len(centres) - 1)]
    left = anchors[0]["x0"] - 6

    def column(w: dict) -> int:
        c = _centre(w)
        for k, b in enumerate(bounds):
            if c < b:
                return k
        return len(centres) - 1

    markets = _name_columns(name_line or [], anchors, column)

    out: list[tuple[str, str, str, float]] = []
    unit = "kg"
    pending: str | None = None
    parent: str | None = None
    for line in lines[start:]:
        name, data = _split(line, left)
        whole = _norm(" ".join(w["text"] for w in line))
        numeric = [w for w in data if _NUM.match(w["text"]) or _RANGE.match(w["text"])]
        if not numeric:
            # A section header, or an item whose numbers wrapped to the next
            # line. Either way it may carry the unit for what follows.
            m = _UNIT_RE.search(whole)
            if m:
                unit = _norm(m.group(1))
            if name:
                pending = _strip_unit(name)[0]
            continue
        if not name:
            name, pending = pending or "", None
        else:
            pending = None
        if not name:
            continue
        if name.startswith("-") and parent:
            # A size continuation of the row above: the bulletin prints
            # "Pineapple - Large" and then bare "- Medium" / "- Small".
            name = _norm(f"{parent} {name}")
        else:
            parent = _norm(name.split(" - ")[0]) or parent
        name, inline_unit = _strip_unit(name)
        row_unit = inline_unit or unit
        if not name:
            continue
        cols: dict[int, list[str]] = defaultdict(list)
        for w in data:
            cols[column(w)].append(w["text"])
        for k, toks in cols.items():
            joined = "".join(toks).replace(" ", "")
            m = _RANGE.match(joined)
            if m:
                price = (float(m.group(1)) + float(m.group(2))) / 2.0
            elif _NUM.match(joined):
                price = float(joined)
            else:
                continue
            if price <= 0:
                continue
            market = markets[k] if k < len(markets) else ""
            if not re.search(r"[A-Za-z]", market):
                # A column whose header word is punctuation (a stray "\\"
                # renders as its own column in a few issues). Without a market
                # there is no identity for the row, so it is not emitted.
                continue
            out.append((name, market, row_unit, price))
    return out


def parse_rice_page(page) -> list[tuple[str, str, str | None, float]]:
    """[(label, market, unit, average_price)] from the rice / subsidiary table.

    Only the AVERAGE column is emitted; the range and the day-on-day change
    are not prices in their own right."""
    lines = _lines(page)
    header = None
    start = 0
    for i, line in enumerate(lines):
        texts = [w["text"] for w in line]
        if "Average" in texts and "Range" in texts:
            header, start = line, i + 1
            break
    if header is None:
        return []
    averages = [w for w in header if w["text"] == "Average"]
    if not averages:
        return []
    market_line = None
    for line in lines[:start]:
        if any(w["text"] == "Pettah" for w in line):
            market_line = line
    market_names = []
    for a in averages:
        if market_line:
            best = min(market_line, key=lambda w: abs(_centre(w) - _centre(a)))
            market_names.append(_market_name(best["text"]))
        else:
            market_names.append("")
    centres = [_centre(w) for w in averages]
    left = min(w["x0"] for w in header) - 8

    out: list[tuple[str, str, str | None, float]] = []
    unit: str | None = None
    section: str | None = None
    pending: str | None = None
    for line in lines[start:]:
        name, data = _split(line, left)
        whole = _norm(" ".join(w["text"] for w in line))
        numeric = [w for w in data if _NUM.match(w["text"])]
        if not numeric:
            m = _UNIT_RE.search(whole)
            if m:
                # A unit-bearing section header: "Rice (Rs/50 kg)",
                # "Eggs (Rs/Egg)". The unit is era-dependent and load-bearing.
                unit = _norm(m.group(1))
                stripped = _norm(_UNIT_RE.sub("", whole))
                section = stripped or section
                pending = None
                continue
            if name:
                if _key(name) in _RICE_SECTIONS:
                    section, pending = name, None
                else:
                    pending = name
            continue
        if not name:
            name, pending = pending or "", None
        else:
            # A held line is only a section when it is one of the table's own
            # unit-less headings. Promoting any held line turned a rice grade
            # that happened to be priced nowhere that day into a section and
            # produced labels like "Samba 3 - Nadu 2".
            pending = None
        if not name:
            continue
        label = name if (not section or _key(section) == _key(name)) else f"{section} - {name}"
        for k, a in enumerate(centres):
            near = [w for w in data if _NUM.match(w["text"]) and abs(_centre(w) - a) < 26]
            if not near:
                continue
            w = min(near, key=lambda w: abs(_centre(w) - a))
            price = float(w["text"])
            if price > 0:
                out.append((label, market_names[k], unit, price))
    return out


def _bulletins(session) -> list[tuple[date, str]]:
    resp = session.get(_INDEX_URL, timeout=180)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    out: list[tuple[date, str]] = []
    seen: set[str] = set()
    for tr in soup.find_all("tr"):
        cells = tr.find_all(["td", "th"])
        if not cells:
            continue
        m = _DATE_RE.match(_norm(cells[0].get_text()))
        a = tr.find("a", href=True)
        if not m or a is None:
            continue
        href = a["href"]
        if href in seen:
            continue
        seen.add(href)
        url = href if href.startswith("http") else _BASE + urllib.parse.quote(href.lstrip("/"))
        out.append((date(int(m.group(1)), int(m.group(2)), int(m.group(3))), url))
    return out


def _fetch_one(args):
    session, obs, url = args
    try:
        resp = session.get(url, timeout=300)
        resp.raise_for_status()
        return obs, url, resp.content
    except Exception:
        logger.warning("%s: could not download %s -- skipping", _SOURCE_KEY, url)
        return obs, url, None


def fetch_lk_harti_daily_prices(cutoff: date) -> pd.DataFrame | None:
    import pdfplumber

    session = get_session()
    session.verify = False

    todo = [(obs, url) for obs, url in _bulletins(session) if obs > cutoff]
    if not todo:
        logger.info("%s: no bulletins newer than %s", _SOURCE_KEY, cutoff)
        return None
    todo.sort()
    logger.info("%s: %d bulletin(s) to read", _SOURCE_KEY, len(todo))

    rows: list[dict] = []
    unknown: dict[str, int] = defaultdict(int)
    no_unit: dict[str, int] = defaultdict(int)
    failures = 0
    scrape_ts = get_scrape_ts()

    def emit(obs, url, market, label, unit, price, table):
        spec = _COICOP_MAP.get(_key(label))
        if spec is None:
            unknown[label] += 1
            return
        item, coicop = spec
        row = {
            "observation_date": obs.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "subnational_area": market or None,
            "source_key": _SOURCE_KEY,
            "coicop_code": coicop,
            "item_name": item,
            "price_local": round(price, 2),
            "currency": _CURRENCY,
            "unit": unit,
            "source_url": url,
            "notes": table,
            "scrape_ts": scrape_ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        for obs, url, blob in pool.map(
            _fetch_one, [(session, obs, url) for obs, url in todo]
        ):
            if blob is None:
                failures += 1
                continue
            try:
                with pdfplumber.open(io.BytesIO(blob)) as pdf:
                    pages = list(pdf.pages)
                    for page in pages:
                        text = page.extract_text() or ""
                        if "Average" in text and "Range" in text:
                            for label, market, unit, price in parse_rice_page(page):
                                if unit is None:
                                    # The section header that carries the unit
                                    # failed to render. "Rs/50 kg" and "Rs/kg"
                                    # both occur in this archive, so a guessed
                                    # unit would be a silent 50x error.
                                    no_unit[label] += 1
                                    continue
                                emit(obs, url, market, label, _canon_unit(unit), price,
                                     "wholesale market average, rice & subsidiary food crops")
                        elif "Variety" in text and "Market" in text:
                            for label, market, unit, price in parse_market_page(page):
                                emit(obs, url, market, label, _canon_unit(unit), price,
                                     "wholesale market range midpoint, selected markets")
            except Exception:
                failures += 1
                logger.warning("%s: could not parse %s -- skipping", _SOURCE_KEY, url)

    if unknown:
        top = sorted(unknown.items(), key=lambda kv: -kv[1])[:40]
        logger.warning(
            "%s: %d unmapped label(s), %d row(s) dropped; most frequent: %s",
            _SOURCE_KEY, len(unknown), sum(unknown.values()),
            "; ".join(f"{k} x{v}" for k, v in top),
        )
    if no_unit:
        logger.warning(
            "%s: %d row(s) dropped for an unreadable unit header, over %d label(s)",
            _SOURCE_KEY, sum(no_unit.values()), len(no_unit),
        )
    if failures:
        logger.warning("%s: %d bulletin(s) failed to download or parse", _SOURCE_KEY, failures)
    if not rows:
        return None
    df = pd.DataFrame(rows)
    before = len(df)
    df = df.drop_duplicates(subset="observation_hash", keep="first")
    if len(df) != before:
        logger.info("%s: dropped %d duplicate row(s)", _SOURCE_KEY, before - len(df))
    return df
