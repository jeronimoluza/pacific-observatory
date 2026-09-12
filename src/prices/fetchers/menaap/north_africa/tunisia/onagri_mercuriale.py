"""ONAGRI Tunisia -- monthly wholesale mercuriale of the Bir El Kassaa
national-interest market (Marche de gros de Bir El Kassaa).

ONAGRI (Observatoire National de l'Agriculture) publishes, once a month, a
JasperReports HTML export titled "Mercuriale Bir El Kassaa <mois> <annee>"
carrying the market's wholesale averages for fruit, vegetables and fish.
Bir El Kassaa is Tunisia's principal wholesale produce market, so these are
national reference wholesale prices, not a retail survey.

DISCOVERY
---------
The landing page is `/Marche-de-gros-bir-el-kasaa/fr/62`. `/fr/62` on its own
is a 404 -- the slug segment is load-bearing. The index renders an HTML table
of issues, each an `<a>` whose text is the French month and year and whose
href is `/uploads/<epoch>_<hash>.html`. The hash gives no clue about the
period, so the LINK TEXT is the only date source and the fetcher reads it.

The index paginates (`?limit=N&page=N`) and its pager advertises 19 pages at
limit=10, but that count is wrong: at limit=100 page 1 returns every issue the
section holds and page 3 returns nothing. Measured 2026-09-11: SEVEN issues,
January..July 2026. The pager is walked anyway, defensively, until a page
yields no new upload link.

DOCUMENT SHAPE
--------------
Each issue is a JasperReports HTML export -- `<table class="jrPage">`, one per
printed page, three pages per issue. Rows are laid out in SOURCE order, which
for this RTL report puts the commodity name LAST:

    [ days, price-change %, price Y-1, price Y, supply-change %, qty Y-1, qty Y, NAME ]

A row whose quantity columns are empty is shorter and reads

    [ days, price-change %, price Y-1, price Y, NAME ]

so the name is taken from `cells[-1]` and never from a fixed index. Rows with a
single cell are section headers (الغلال fruit / الخضر vegetables / الأسماك
fish) and set the active section, which is what the COICOP map is keyed on
second.

The column order (previous year before current year) is not assumed: it is
CHECKED per row. `cells[1]` is the publisher's own year-on-year price change,
so `_consistent()` verifies that (price_Y / price_Y-1 - 1) reproduces it to
within 2 points before either value is emitted. On the July 2026 issue every
row passes; a row that fails is dropped rather than emitted with a possibly
transposed year.

EACH ISSUE YIELDS TWO YEARS. The mercuriale is a comparison table, so a single
2026 issue carries both the 2026 month and the same month of 2025. The archive
holds no 2025 issues at all, so emitting the comparison column is the only way
this source reaches 2025 -- it doubles the series for free. Both rows carry
`period_kind: monthly_avg`; `notes` records which column a row came from.

UNITS
-----
Prices are published in MILLIMES per kilogram ("معدل الأسعار (مليم/كلغ)"), and
1 TND = 1000 millimes, so every value is divided by 1000 before emission. This
is the 1000x trap the skill warns about: figs at "8 000" are TND 8.00/kg, not
TND 8000/kg. Quantities (tonnes/month) are read only for the consistency check
and are not emitted -- they are not prices.

COICOP
------
`_COICOP_MAP` is keyed on the Arabic commodity string exactly as the report
renders it (after whitespace normalisation -- the export pads some names with
tatweel and non-breaking spaces, e.g. "قــارص", "تفـاح"). An unmapped name is
logged and DROPPED, never emitted with a guessed code.

`coicop_classification` is `classifier` in the manifest while this module
stamps a per-row `coicop_code`. That pairing is deliberate and is the same one
`zm_mfl_market_bulletin` carries: `concatenate._build_classifier_csv_map`
ingests a fetcher's price_observations.csv ONLY for `classifier` sources, so
declaring `source_curated` would remove this file from the corpus entirely.
The per-row code rides through as `declared_coicop_codes` and short-circuits
the classifier head at confidence 1.0.

Emits PriceObservation rows.
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_INDEX_URL = "https://www.onagri.nat.tn/Marche-de-gros-bir-el-kasaa/fr/62"
_COUNTRY = "Tunisia"
_CURRENCY = "TND"
_SOURCE_KEY = "tn_onagri_mercuriale"
_MARKET = "Bir El Kassaa wholesale market, Ben Arous"

_IDENT = ["source_key", "observation_date", "subnational_area", "item_name"]

# Millimes per dinar. Every published price is in millimes/kg.
_MILLIMES_PER_DINAR = 1000.0

_FR_MONTHS = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11,
    "decembre": 12,
}

# Arabic section headers -> a short English label kept in `notes`.
_SECTIONS = {
    "الغلال": "fruit",
    "الخضر": "vegetables",
    "الأسماك": "fish",
}

# Normalised Arabic commodity -> (English item_name, COICOP-2018 leaf).
#
# Unidentifiable-but-in-section entries ("غلال أخرى" / "خضر أخرى" /
# "أسماك أخرى") go to their section's n.e.c. leaf, which is what those leaves
# are for; they are NOT dropped, because "other fresh fruit" is a true
# statement about them. Species whose exact taxon is uncertain (the Tunisian
# vernacular fish names) go to "other fish, live/fresh" -- correct at leaf
# grain for any finfish, and the section guarantees they are finfish.
_COICOP_MAP = {
    # -- fruit (الغلال) ------------------------------------------------
    "تين": ("Figs, fresh (wholesale)", "01.1.6.1.4"),
    "دقلة": ("Deglet Nour dates (wholesale)", "01.1.6.1.3"),
    "قارص": ("Citrus fruit, fresh (wholesale)", "01.1.6.2.9"),
    "برتقال مسكي": ("Oranges, Meski (wholesale)", "01.1.6.2.3"),
    "برتقال طمسون": ("Oranges, Thomson (wholesale)", "01.1.6.2.3"),
    "برتقال صيفي": ("Oranges, summer (wholesale)", "01.1.6.2.3"),
    "برتقال مالطي": ("Oranges, Maltaise (wholesale)", "01.1.6.2.3"),
    "مالطي قص": ("Oranges, Maltaise demi-sanguine (wholesale)", "01.1.6.2.3"),
    "كليمنتين": ("Clementines (wholesale)", "01.1.6.2.4"),
    "تفاح": ("Apples, fresh (wholesale)", "01.1.6.3.1"),
    "مشمش": ("Apricots, fresh (wholesale)", "01.1.6.3.3"),
    "خوخ": ("Peaches, fresh (wholesale)", "01.1.6.3.5"),
    "خوخ بوطبقاية": ("Flat peaches (wholesale)", "01.1.6.3.5"),
    "عوينة": ("Other stone fruit, fresh (wholesale)", "01.1.6.3.9"),
    "فراولو": ("Strawberries, fresh (wholesale)", "01.1.6.4.5"),
    "عنب": ("Grapes, fresh (wholesale)", "01.1.6.5.1"),
    "بطيخ": ("Melons, fresh (wholesale)", "01.1.6.5.3"),
    "دلاع": ("Watermelons, fresh (wholesale)", "01.1.6.5.4"),
    "غلال أخرى": ("Other fresh fruit (wholesale)", "01.1.6.5.9"),
    "لوز أخضر": ("Green almonds (wholesale)", "01.1.6.8.1"),
    # -- vegetables (الخضر) --------------------------------------------
    "بروكلو": ("Broccoli (wholesale)", "01.1.7.1.3"),
    "قنارية": ("Artichokes (wholesale)", "01.1.7.1.6"),
    "قنارية حمراء": ("Artichokes, red (wholesale)", "01.1.7.1.6"),
    "معدنوس": ("Parsley (wholesale)", "01.1.7.1.9"),
    "بسباس": ("Fennel (wholesale)", "01.1.7.1.9"),
    "فلفل حلو": ("Sweet peppers (wholesale)", "01.1.7.2.1"),
    "فلفل حار": ("Chilli peppers (wholesale)", "01.1.7.2.1"),
    "فقوس": ("Snake cucumber (wholesale)", "01.1.7.2.2"),
    "طماطم": ("Tomatoes (wholesale)", "01.1.7.2.4"),
    "قرع بوطزينة": ("Squash, boutzina (wholesale)", "01.1.7.2.5"),
    "جلبانة": ("Peas, fresh (wholesale)", "01.1.7.3.3"),
    "فول أخضر": ("Broad beans, green (wholesale)", "01.1.7.3.4"),
    "سفنارية": ("Carrots (wholesale)", "01.1.7.4.1"),
    "لفت": ("Turnips (wholesale)", "01.1.7.4.1"),
    "بصل": ("Onions (wholesale)", "01.1.7.4.3"),
    "بصل جاف": ("Onions, dry (wholesale)", "01.1.7.4.3"),
    "بصل أخضر": ("Onions, spring (wholesale)", "01.1.7.4.3"),
    "بصل ربعي": ("Onions, early season (wholesale)", "01.1.7.4.3"),
    "خضر أخرى": ("Other fresh vegetables (wholesale)", "01.1.7.4.9"),
    "بطاطة": ("Potatoes (wholesale)", "01.1.7.5.1"),
    # -- fish (الأسماك) -------------------------------------------------
    "نزلي": ("Hake, fresh (wholesale)", "01.1.3.1.4"),
    "سردينة": ("Sardines, fresh (wholesale)", "01.1.3.1.6"),
    "بوري": ("Grey mullet, fresh (wholesale)", "01.1.3.1.9"),
    "مرجان كركارة": ("Pandora karkara, fresh (wholesale)", "01.1.3.1.9"),
    "مرجان ريشيّة": ("Pandora richiya, fresh (wholesale)", "01.1.3.1.9"),
    "شورو": ("Chouro, fresh (wholesale)", "01.1.3.1.9"),
    "تريليا بيضاء": ("Red mullet, white, fresh (wholesale)", "01.1.3.1.9"),
    "تريلية حمراء": ("Red mullet, fresh (wholesale)", "01.1.3.1.9"),
    "سبارس": ("Sea bream, fresh (wholesale)", "01.1.3.1.9"),
    "غزال": ("Ghazal fish, fresh (wholesale)", "01.1.3.1.9"),
    "أسماك أخرى": ("Other fresh fish (wholesale)", "01.1.3.1.9"),
    "سوبيا": ("Cuttlefish, fresh (wholesale)", "01.1.3.4.4"),
    "قرنيط": ("Octopus, fresh (wholesale)", "01.1.3.4.4"),
}


def _strip_accents(s: str) -> str:
    for a, b in (
        ("é", "e"), ("è", "e"), ("ê", "e"), ("û", "u"), ("ù", "u"), ("ô", "o"),
        ("î", "i"), ("à", "a"), ("â", "a"), ("ç", "c"),
    ):
        s = s.replace(a, b)
    return s


def _norm_ar(s: object) -> str:
    """Collapse whitespace and strip the tatweel the JasperReports export pads
    names with. "قــارص" and "قارص" are the same commodity, and "تفـاح" is
    "تفاح"; without this every issue would key differently."""
    t = str(s or "").replace("ـ", "")           # tatweel
    t = t.replace("\xa0", " ")
    return re.sub(r"\s+", " ", t).strip()


def _issue_date(label: str) -> date | None:
    """Read the period off the index link text, e.g.
    'Mercuriale Bir El Kassaa Juillet 2026'."""
    low = _strip_accents(label.lower())
    year = re.search(r"\b(20\d{2})\b", low)
    if not year:
        return None
    for name, num in _FR_MONTHS.items():
        if name in low:
            return date(int(year.group(1)), num, 1)
    return None


def _number(cell: object) -> float | None:
    raw = str(cell or "").replace("\xa0", "").replace(" ", "").replace(",", ".")
    if not raw or raw in {"-", "--"}:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _percent(cell: object) -> float | None:
    raw = str(cell or "").replace("\xa0", "").replace(" ", "")
    if not raw.endswith("%"):
        return None
    try:
        return float(raw[:-1].replace(",", "."))
    except ValueError:
        return None


def _consistent(prev: float, cur: float, pct: float) -> bool:
    """The publisher's own year-on-year % must reproduce from the two price
    columns. This is what pins down which column is which year -- the report
    is RTL and the header pair ('2025','2026') could in principle be read
    either way round. Tolerance 2 points absorbs the report's own rounding
    (it prints prices to the millime and the percentage to the unit)."""
    if prev <= 0:
        return False
    return abs((cur / prev - 1.0) * 100.0 - pct) <= 2.0


def _issue_links(session) -> dict[str, str]:
    """{absolute issue url: link label}, walking the pager defensively."""
    out: dict[str, str] = {}
    for page in range(1, 21):
        resp = session.get(
            _INDEX_URL, params={"limit": 100, "page": page}, timeout=90, verify=False
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content.decode("utf-8", "replace"), "html.parser")
        added = 0
        for a in soup.find_all("a", href=True):
            label = a.get_text(" ", strip=True)
            href = a["href"]
            if "/uploads/" not in href or not label:
                continue
            if not href.startswith("http"):
                href = "https://www.onagri.nat.tn" + ("" if href.startswith("/") else "/") + href
            if href not in out:
                out[href] = label
                added += 1
        if added == 0:
            break
    return out


def fetch_tn_onagri_mercuriale(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    # The host serves a certificate chain plain `requests` rejects on this box;
    # the pages carry no credentials and no user input, only published tables.
    session.verify = False

    links = _issue_links(session)
    if not links:
        logger.warning("%s: no issues listed at %s", _SOURCE_KEY, _INDEX_URL)
        return None
    logger.info("%s: %d issue(s) listed", _SOURCE_KEY, len(links))

    rows: list[dict] = []
    unknown: set[str] = set()
    for url, label in links.items():
        issue = _issue_date(label)
        if issue is None:
            logger.warning(
                "%s: cannot read a month/year from issue label %r -- skipping",
                _SOURCE_KEY, label,
            )
            continue
        prior = date(issue.year - 1, issue.month, 1)
        # Both columns predate the cutoff -> nothing new in this issue.
        if issue <= cutoff:
            continue

        try:
            resp = session.get(url, timeout=180)
            resp.raise_for_status()
        except Exception:
            logger.warning("%s: could not download %s -- skipping", _SOURCE_KEY, url)
            continue

        soup = BeautifulSoup(resp.content.decode("utf-8", "replace"), "html.parser")
        section: str | None = None
        for page in soup.select("table.jrPage"):
            for tr in page.select("tr"):
                cells = [
                    _norm_ar(td.get_text(" ", strip=True))
                    for td in tr.find_all("td", recursive=False)
                ]
                cells = [c for c in cells if c]
                if not cells:
                    continue
                if len(cells) == 1:
                    if cells[0] in _SECTIONS:
                        section = _SECTIONS[cells[0]]
                    continue
                if len(cells) < 5:
                    continue
                days = _number(cells[0])
                pct = _percent(cells[1])
                prev_price = _number(cells[2])
                cur_price = _number(cells[3])
                if days is None or pct is None or prev_price is None or cur_price is None:
                    continue
                name = cells[-1]
                spec = _COICOP_MAP.get(name)
                if spec is None:
                    unknown.add(f"{section}:{name}")
                    continue
                if not _consistent(prev_price, cur_price, pct):
                    logger.warning(
                        "%s: %s %s -- %s/%s does not reproduce %s%%, dropping",
                        _SOURCE_KEY, issue, name, prev_price, cur_price, pct,
                    )
                    continue
                item, coicop = spec
                for obs, millimes, which in (
                    (prior, prev_price, "prior-year comparison column"),
                    (issue, cur_price, "reporting-month column"),
                ):
                    if obs <= cutoff:
                        continue
                    row = {
                        "observation_date": obs.isoformat(),
                        "period_kind": "monthly_avg",
                        "country": _COUNTRY,
                        "subnational_area": _MARKET,
                        "source_key": _SOURCE_KEY,
                        "coicop_code": coicop,
                        "item_name": item,
                        "price_local": round(millimes / _MILLIMES_PER_DINAR, 3),
                        "currency": _CURRENCY,
                        "unit": "kg",
                        "source_url": url,
                        "notes": f"{section or 'unknown'}; {which}; {int(days)} trading days",
                        "scrape_ts": get_scrape_ts(),
                        "observation_hash": None,
                    }
                    row["observation_hash"] = make_hash(row, _IDENT)
                    rows.append(row)

    if unknown:
        logger.warning(
            "%s: %d unmapped commodity name(s), not emitted: %s",
            _SOURCE_KEY, len(unknown), "; ".join(sorted(unknown)),
        )
    if not rows:
        return None
    df = pd.DataFrame(rows)
    before = len(df)
    df = df.drop_duplicates(subset="observation_hash", keep="first")
    if len(df) != before:
        logger.info("%s: dropped %d duplicate row(s)", _SOURCE_KEY, before - len(df))
    return df
