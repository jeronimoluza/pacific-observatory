"""Zambia Ministry of Fisheries and Livestock -- National MFL Market Bulletin:
monthly indicative prices for dairy, fish, poultry, eggs and meat, published
per province and as a national average.

Compiled by the Fisheries and Livestock Marketing Department from returns sent
in by all ten provincial centres. The bulletin's own wording for the per-
province figures is "MONTHLY PROVINCIAL INDICATIVE PRICE" and for the bottom
row "NATIONAL AVERAGE INDICATIVE PRICE" -- market prices, monthly, not a
survey of named outlets.

DISCOVERY
---------
The archive is NOT reachable the usual WordPress ways: `/wp-json/wp/v2/media`
returns HTTP 500 on this host, `/wp-sitemap.xml` likewise, and the home page
carries no PDF links at all. The list lives on one ordinary page, "Market
Bulletin" in the Resource Library, at `?page_id=543`; the fetcher reads that
page and takes every `*.pdf` href. Measured 2026-09-11: 43 bulletins, July
2022 to 2026. The page's own links are `http://` (not https) and are left as
published.

Filenames are inconsistent -- `NATIONAL-MARKET-BULLETIN-APRIL-2023.pdf`,
`NATIONAL-MFL-MARKET-BULLETIN-MAY-2026.pdf`,
`...-APRIL-2026-TRADE-DATA.pdf`, and one (`...-MARCH-final-copy.pdf`) that
carries no year at all -- so the month is read from the DOCUMENT text first
(its table captions end "... - MAY-2026") and only falls back to the filename.
A bulletin whose month cannot be established either way is skipped with a
warning rather than dated by guesswork.

TLS
---
`www.mfl.gov.zm` serves ONE certificate and no intermediate -- `openssl
s_client -showcerts` returns a single leaf, `CN=grz.gov.zm`, whose subject
does not even name this host ("verify error:num=20: unable to get local
issuer certificate", then num=21). That is a server misconfiguration, not a
transient block: every TLS client fails verification identically. So
`verify=False` is required and is load-bearing, not defensive -- the same
treatment `cie_tariff.py` and `stattj_cpi.py` already carry for the same
defect. The pages carry no credentials and no user input, only published
bulletins.

PARSING
-------
`pdfplumber.extract_tables()` reads these cleanly; the tables are ruled and
the OCR path is not needed. Two structural facts drive the parser:

  * A table's header row and its body are frequently split across a PAGE
    BOUNDARY -- in the May-2026 issue the fish header ("PROVINCE | Fresh
    Bream per Kg | ...") is the entire table on page 4 and the province rows
    are a separate table on page 5. So tables are walked in document order and
    the most recent row whose first cell is "PROVINCE" is carried forward as
    the active header.
  * Every price table is shadowed by a second table keyed on "MONTH"
    (this month, last month, % change). Those are ignored: they restate the
    national average already read from the "AVERAGE" row, and the % change
    row is not a price.

Header cells contain embedded newlines from the wrapped layout ("Fresh\\nKapent\\na
per\\nKg"), so they are whitespace-normalised before lookup. Only columns
present in `_COLUMNS` are emitted; an unrecognised header is logged and
skipped rather than emitted with a guessed unit, because the unit lives in the
header text and differs column to column within one table -- per litre, per
kg, each, per tray. Cells the province did not report render "-" and are
skipped.

COICOP
------
`_COLUMNS` maps each normalised header to (item_name, unit, COICOP-2018 leaf).
Live animals go to the 01.1.2.1.x live-animal leaves and carcass cuts to
01.1.2.2.x, which is the distinction the bulletin itself draws ("LIVE PIGS",
"LIVE GOAT", "VILLAGE CHICKEN EACH" against "DRESSED CHICKEN/kg", "PORK/KG").
Offal and hooves go to 01.1.2.4.0. Sour milk goes to 01.1.4.6.0 following this
project's existing yoghurt convention (fermented milk -> 01.1.4.6.0);
long-life milk goes to the preserved-milk leaf 01.1.4.3.9 rather than to the
whole-milk leaf used for fresh.

The day-old-chick and point-of-lay columns are deliberately left OUT of
`_COLUMNS`: they are livestock inputs, not household consumption, the same
call made for the animal-feed tail in stat_uz_avg_prices.

`_COLUMNS` stamps a per-COLUMN COICOP leaf while the manifest stays
`coicop_classification: classifier`. That pairing is deliberate:
`concatenate`'s `_build_classifier_csv_map` ingests a fetcher's
price_observations.csv ONLY for `classifier` sources, so declaring
`source_curated` would remove this file from the corpus altogether; the
per-row code instead rides through as `declared_coicop_codes` and
short-circuits the head in `classify` (`state=narrow_source`, confidence 1.0).

Emits PriceObservation rows.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_INDEX_URL = "https://www.mfl.gov.zm/?page_id=543"
_COUNTRY = "Zambia"
_CURRENCY = "ZMW"
_SOURCE_KEY = "zm_mfl_market_bulletin"

_IDENT = ["source_key", "observation_date", "subnational_area", "item_name"]

_PDF_HREF_RE = re.compile(r'href="(https?://[^"]*\.pdf)"', re.I)
_MONTHS = {
    "JANUARY": 1, "FEBRUARY": 2, "MARCH": 3, "APRIL": 4, "MAY": 5, "JUNE": 6,
    "JULY": 7, "AUGUST": 8, "SEPTEMBER": 9, "OCTOBER": 10, "NOVEMBER": 11,
    "DECEMBER": 12,
}
_MONTH_YEAR_RE = re.compile(
    r"\b(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER"
    r"|NOVEMBER|DECEMBER)[\s\-_]*(20\d{2})\b",
    re.I,
)

_PROVINCES = {
    "LUSAKA": "Lusaka",
    "COPPERBELT": "Copperbelt",
    "CENTRAL": "Central",
    "EASTERN": "Eastern",
    "LUAPULA": "Luapula",
    "MUCHINGA": "Muchinga",
    "NORTHERN": "Northern",
    "NORTHWESTERN": "North Western",
    "SOUTHERN": "Southern",
    "WESTERN": "Western",
}

# Normalised header cell (upper-case, whitespace removed) ->
# (item_name, unit, COICOP-2018 leaf).
_COLUMNS = {
    # dairy
    "FRESHMILKPERLITRE(K)": ("Fresh milk", "L", "01.1.4.1.1"),
    "LONG-LIFEMILKPERLITRE(K)": ("Long-life milk", "L", "01.1.4.3.9"),
    "SOURMILKPERLITRE(K)": ("Sour milk", "L", "01.1.4.6.0"),
    # capture fishery
    "FRESHBREAMPERKG": ("Fresh bream", "kg", "01.1.3.1.1"),
    "FRESHKAPENTAPERKG": ("Fresh kapenta", "kg", "01.1.3.1.1"),
    "DRYKAPENTAPERKG": ("Dry kapenta", "kg", "01.1.3.2.9"),
    "BUKABUKAPERKG": ("Buka buka", "kg", "01.1.3.1.1"),
    "HORSEMACKERELPERKG": ("Horse mackerel", "kg", "01.1.3.1.6"),
    # aquaculture output (the farmed-fish table's marketable grade)
    "TABLESIZE(WHOLESALEPRICE\u2013KG)": ("Table-size farmed fish", "kg", "01.1.3.1.1"),
    "TABLESIZEPRICE\u2013KG)": ("Table-size farmed fish", "kg", "01.1.3.1.1"),
    # poultry, eggs, small livestock (live animals)
    "VILLAGECHICKENEACH(K)": ("Village chicken, live", "each", "01.1.2.1.4"),
    "BROILERCHICKENEACH(K)": ("Broiler chicken, live", "each", "01.1.2.1.4"),
    "CULLEDLAYERSEACH(K)": ("Culled layer, live", "each", "01.1.2.1.4"),
    "CHICKENEGGS/TRAY(K)": ("Chicken eggs", "tray", "01.1.4.8.1"),
    "DRESSEDCHICKEN/KG": ("Dressed chicken", "kg", "01.1.2.2.4"),
    "LIVEPIGS": ("Pig, live", "each", "01.1.2.1.2"),
    "LIVEPIG": ("Pig, live", "each", "01.1.2.1.2"),
    "LIVEPIG(K)": ("Pig, live", "each", "01.1.2.1.2"),
    "PIGS(EACH)": ("Pig, live", "each", "01.1.2.1.2"),
    "PIGS(HYBRID)": ("Pig, live, hybrid", "each", "01.1.2.1.2"),
    "LIVEGOAT": ("Goat, live", "each", "01.1.2.1.3"),
    "LIVEGOAT(K)": ("Goat, live", "each", "01.1.2.1.3"),
    "GOATS(EACH)": ("Goat, live", "each", "01.1.2.1.3"),
    # meat
    "STEAK/KG": ("Beef steak", "kg", "01.1.2.2.1"),
    "MIXEDCUT/KG": ("Beef mixed cut", "kg", "01.1.2.2.1"),
    "MIXEDT/CUT/KG": ("Beef mixed cut", "kg", "01.1.2.2.1"),
    "T/BONE/KG": ("Beef T-bone", "kg", "01.1.2.2.1"),
    "BEEFOFFALS/KG": ("Beef offals", "kg", "01.1.2.4.0"),
    "BONE/KG": ("Bone", "kg", "01.1.2.4.0"),
    "HOOVES/KG": ("Hooves", "kg", "01.1.2.4.0"),
    "CHEVON/KG": ("Chevon (goat meat)", "kg", "01.1.2.2.3"),
    "GOAT/KG": ("Chevon (goat meat)", "kg", "01.1.2.2.3"),
    "PORK/KG": ("Pork", "kg", "01.1.2.2.2"),
}

# Columns that are livestock / aquaculture INPUTS rather than household
# consumption (the same call made for the animal-feed tail in
# stat_uz_avg_prices), plus non-price columns. Listed so they are skipped
# silently instead of logging an "unknown header" warning on every issue.
_INPUT_COLUMNS = frozenset(
    {
        "",
        "PROVINCE",
        "MONTH",
        "COMMENT",
        "NAMEOFHATCHERY/SUPPLIER",
        "FARMINGFARM",
        "DAY-OLDCHICKSEACH-(BROILER)",
        "DAY-OLDCHICKSEACH(BROILER)",
        "DAY-OLDCHICKSEACH(LAYERS)",
        "DAY-OLDCHICKSEACH-(LAYERS)",
        "POINTOFLAY(PULLETS)EACH",
        "POINTOFLAYPULLETSEACH",
        "FINGERLINGS\u2013EACH",
        "BROODSTOCKPER",
        "BROODSTOCKPERSETOF(1MALE;3FEMALES)",
        "STARTERX50",
        "STARTERX50KG",
        "GROWERX50",
        "GROWERX50KG",
        "FINISHERX",
        "FINISHERX50KG",
    }
)


def _norm(cell: object) -> str:
    """Upper-case with ALL whitespace removed.

    Header cells are not merely wrapped between words -- the PDF wraps INSIDE
    a word, so one issue's beef column reads "STEA\nK/KG" and another's
    "STEAK\n/KG", and the mixed-cut column appears as "MIXE\nD CUT/\nKG".
    Collapsing runs of whitespace is therefore not enough; the space has to go
    entirely, or the same column is a different key in every issue. Measured:
    collapsing alone left 58 unmatched header variants across the 43
    bulletins, nearly all of them re-spellings of columns already mapped.
    """
    return re.sub(r"\s+", "", str(cell or "")).upper()


def _bulletin_date(text: str, url: str) -> date | None:
    for haystack in (text, url):
        m = _MONTH_YEAR_RE.search(haystack or "")
        if m:
            return date(int(m.group(2)), _MONTHS[m.group(1).upper()], 1)
    return None


def _price(cell: object) -> float | None:
    raw = str(cell or "").strip().replace(",", "").replace(" ", "")
    if not raw or raw in {"-", "--", "N/A", "NA"}:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def fetch_zm_mfl_market_bulletin(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    # See the TLS note in the module docstring: this host serves a single
    # mis-named leaf certificate with no intermediate, so verification can
    # never succeed.
    session.verify = False
    index = session.get(_INDEX_URL, timeout=90)
    index.raise_for_status()
    urls = sorted(set(_PDF_HREF_RE.findall(index.text)))
    urls = [u for u in urls if "BULLETIN" in u.upper()]
    if not urls:
        logger.warning("%s: no bulletin PDFs listed on %s", _SOURCE_KEY, _INDEX_URL)
        return None

    import pdfplumber

    rows: list[dict] = []
    unknown: set[str] = set()
    for url in urls:
        try:
            resp = session.get(url, timeout=300)
            resp.raise_for_status()
        except Exception:
            logger.warning("%s: could not download %s -- skipping", _SOURCE_KEY, url)
            continue
        try:
            with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
                text = "\n".join(p.extract_text() or "" for p in pdf.pages)
                tables = [t for p in pdf.pages for t in p.extract_tables()]
        except Exception:
            logger.warning("%s: could not parse %s -- skipping", _SOURCE_KEY, url)
            continue

        obs = _bulletin_date(text, url)
        if obs is None:
            logger.warning(
                "%s: no month/year in document text or filename for %s -- skipping",
                _SOURCE_KEY,
                url,
            )
            continue
        if obs <= cutoff:
            continue

        header: list[str] | None = None
        for table in tables:
            for raw_row in table:
                cells = [_norm(c) for c in raw_row]
                if not cells or not any(cells):
                    continue
                if cells[0] == "PROVINCE":
                    header = cells
                    continue
                if cells[0] == "MONTH":
                    # the shadow table (this month / last month / % change)
                    header = None
                    continue
                if header is None:
                    continue
                first = cells[0].replace("PROVINCE", "").strip()
                if first == "AVERAGE":
                    area = None
                elif first in _PROVINCES:
                    area = _PROVINCES[first]
                else:
                    continue
                for col, value in zip(header[1:], raw_row[1:]):
                    if col in _INPUT_COLUMNS:
                        continue
                    spec = _COLUMNS.get(col)
                    if spec is None:
                        unknown.add(col)
                        continue
                    price = _price(value)
                    if price is None:
                        continue
                    item, unit, coicop = spec
                    row = {
                        "observation_date": obs.isoformat(),
                        "period_kind": "monthly_avg",
                        "country": _COUNTRY,
                        "subnational_area": area,
                        "source_key": _SOURCE_KEY,
                        "coicop_code": coicop,
                        "item_name": item,
                        "price_local": price,
                        "currency": _CURRENCY,
                        "unit": unit,
                        "source_url": url,
                        "notes": "national average indicative price"
                        if area is None
                        else "provincial indicative price",
                        "scrape_ts": get_scrape_ts(),
                        "observation_hash": None,
                    }
                    row["observation_hash"] = make_hash(row, _IDENT)
                    rows.append(row)

    if unknown:
        logger.warning(
            "%s: %d unmapped column header(s), not emitted: %s",
            _SOURCE_KEY,
            len(unknown),
            "; ".join(sorted(unknown)),
        )
    if not rows:
        return None
    df = pd.DataFrame(rows)
    # Some months are published twice (e.g. a "-final-copy" re-issue) and a
    # table occasionally repeats a province row across a page break. The
    # writer only de-duplicates against what is already on disk, not within
    # the incoming frame, so collapse identical hashes here.
    before = len(df)
    df = df.drop_duplicates(subset="observation_hash", keep="first")
    if len(df) != before:
        logger.info("%s: dropped %d duplicate row(s)", _SOURCE_KEY, before - len(df))
    return df
