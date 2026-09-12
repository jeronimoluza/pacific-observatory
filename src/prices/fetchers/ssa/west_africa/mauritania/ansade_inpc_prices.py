"""ANSADE Mauritania -- average RETAIL prices of essential products, from the
monthly INPC bulletin.

ANSADE (Agence Nationale de la Statistique et de l'Analyse Demographique et
Economique) publishes a monthly "Note mensuelle de l'Indice National des Prix a
la Consommation". Most of the note is index material, but the bulletins carry a
"Tableau 3 : Prix moyens en MRU de detail de quelques produits essentiels au
niveau des centres de l'INPC" -- thirteen basket items priced in MRU at each of
the five INPC collection centres (Aioun, Rosso, Atar, Nouadhibou, Nouakchott).
Those are price LEVELS, and they are what this fetcher emits. The index tables
in the same document are a different schema and a different source.

DISCOVERY
---------
`https://admin.ansade.mr/wp-json/ansade/v1/publications/` is an unauthenticated
WordPress JSON route returning all 531 publications in one 11 MB response, each
with `title`, `date`, `categories`, a `file` object, and a `pdf_content` field
carrying the document's extracted text. 177 publications sit in the "Prix"
category; 128 of those are INPC notes; 78 of THOSE carry Tableau 3 (measured
2026-09-11, coverage 2016-01 to 2022-07).

`pdf_content` is populated for only the most recent ~35 publications -- it is
empty string for everything older -- so the fetcher falls back to downloading
`file.url` and reading it with pdfplumber. It prefers `pdf_content` when
present because that costs no request at all.

DATING
------
Two independent sources, used in that order:
  1. the table's own caption, "... centres de l'INPC en juillet 2022";
  2. the publication title, "... (INPC) Janvier 2016".
Neither alone is sufficient: the caption is absent from the ten 2016 notes,
and the title is empty of any month on several 2024-2026 notes. The WordPress
`date` field is the PUBLICATION date (a note for August is published in
September) and is never used as the observation date. A note whose month cannot
be established either way is skipped with a warning.

The title is also read BEFORE the PDF is fetched, so a re-run skips the
download entirely for every month already on disk.

PARSING
-------
The bulletins are bilingual French/Arabic with the Arabic column printed to the
right of the French one, so every extracted line ends in Arabic text plus
leftover bracket debris (`) (`, `) 21 (`, and on one row `) ( ) (`). Arabic
characters are stripped and the trailing bracket residue removed before the row
is matched; without that, anchoring the five values to end-of-line fails on
every row and the table reads as empty.

Rows are `<French label> <5 values>`, one value per collection centre in the
header's order. Labels may themselves contain digits ("bouteille de 12,5 Kg de
gaz"), so the label is matched non-greedily against a fixed five-value tail
rather than by splitting on the first number. Unavailable cells are published
as "nd" / "ND" and are skipped.

COICOP
------
Thirteen stable items, hand-mapped in `_COICOP_MAP`; an unmapped label is
logged and DROPPED. Ten are food (division 01), two are LPG bottle refills
(04.5.2.2, liquefied hydrocarbons) and one is road diesel (07.2.2.1) -- so this
one small table reaches three divisions.

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
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_API_URL = "https://admin.ansade.mr/wp-json/ansade/v1/publications/"
_COUNTRY = "Mauritania"
_CURRENCY = "MRU"
_SOURCE_KEY = "mr_ansade_inpc_prices"

_IDENT = ["source_key", "observation_date", "subnational_area", "item_name"]

_WORKERS = 6

_MONTHS = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11,
    "decembre": 12,
}

# Arabic script blocks, plus the Arabic presentation forms the PDFs use.
_ARABIC = re.compile("[؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿]")
# Bracket debris left where the Arabic column was, e.g. ") (", ") 21 (".
_BRACKET_TAIL = re.compile(r"(?:\s*\)[\s\d,.]*\()+\s*$")

_VALUE = r"(?:nd|ND|n\.?d\.?|-{1,2}|\d+(?:[,.]\d+)?)"
_ROW = re.compile(r"^(.*?[A-Za-zÀ-ÿœŒ)])\s+((?:" + _VALUE + r"\s+){4}" + _VALUE + r")$")
_CAPTION = re.compile(r"INPC\s+en\s+([A-Za-zÀ-ÿ]+)\s*(\d{4})", re.I)
_TITLE_MONTH = re.compile(r"([A-Za-zÀ-ÿ]+)\s*[-–]?\s*(\d{4})\s*$")
_TABLE3 = re.compile(r"Prix moyens.{0,80}d[eé]tail", re.S)

# The five INPC collection centres, in the order the table's header prints
# them. The header is identical in all 78 bulletins; it is re-read per document
# anyway and a document whose header does not match is skipped.
_CENTRES = ["Aioun", "Rosso", "Atar", "Nouadhibou", "Nouakchott"]

# French label -> (item_name, unit, COICOP-2018 leaf).
_COICOP_MAP = {
    "riz importe (yebregh) (kg)": ("Rice, imported (yebregh)", "kg", "01.1.1.1.2"),
    "couscous local de ble (kg)": ("Couscous, local wheat", "kg", "01.1.1.5.0"),
    "farine de ble (kg)": ("Wheat flour", "kg", "01.1.1.2.1"),
    "viande de boeuf fraiche avec os (kg)": ("Beef, fresh, bone-in", "kg", "01.1.2.2.1"),
    "viande de chameau, fraiche avec os (kg)": ("Camel meat, fresh, bone-in", "kg", "01.1.2.2.7"),
    "dorade frais (kibarou) (kg)": ("Sea bream (kibarou), fresh", "kg", "01.1.3.1.9"),
    "poisson frais courbine (sigh) (kg)": ("Meagre (sigh), fresh", "kg", "01.1.3.1.9"),
    "banane douce (kg)": ("Bananas", "kg", "01.1.6.1.2"),
    "pomme (kg)": ("Apples", "kg", "01.1.6.3.1"),
    "datte importee (kg)": ("Dates, imported", "kg", "01.1.6.1.3"),
    "oignon frais (kg)": ("Onions, fresh", "kg", "01.1.7.4.3"),
    "chargement d'une bouteille de 12,5 kg de gaz": (
        "LPG refill, 12.5 kg bottle", "12.5 kg bottle", "04.5.2.2"),
    "chargement d'une bouteille de 3 kg de gaz": (
        "LPG refill, 3 kg bottle", "3 kg bottle", "04.5.2.2"),
    "gas-oil (litre)": ("Diesel (gas-oil)", "L", "07.2.2.1"),
}


def _fold(s: object) -> str:
    """Lower-case, accent-fold and collapse whitespace. The bulletins spell the
    same label with and without accents across eras ("Datte importee" /
    "Datte importée"), so the map is keyed on the folded form."""
    t = str(s or "")
    for a, b in (
        ("é", "e"), ("è", "e"), ("ê", "e"), ("ë", "e"), ("à", "a"), ("â", "a"),
        ("î", "i"), ("ï", "i"), ("ô", "o"), ("ö", "o"), ("û", "u"), ("ù", "u"),
        ("ü", "u"), ("ç", "c"), ("œ", "oe"), ("’", "'"),
    ):
        t = t.replace(a, b).replace(a.upper(), b)
    return re.sub(r"\s+", " ", t).strip().lower()


def _month_from(text: str, pattern: re.Pattern) -> date | None:
    m = pattern.search(_fold(text))
    if not m:
        return None
    num = _MONTHS.get(m.group(1))
    if not num:
        return None
    return date(int(m.group(2)), num, 1)


def _clean(line: str) -> str:
    out = _ARABIC.sub(" ", line)
    out = re.sub(r"\s+", " ", out).strip()
    return _BRACKET_TAIL.sub("", out).strip()


def _parse_table3(text: str) -> list[tuple[str, list[str]]]:
    start = text.find("PRODUITS")
    if start < 0:
        start = text.find("Prix moyens")
    if start < 0:
        return []
    rows: list[tuple[str, list[str]]] = []
    for raw in text[start : start + 4000].split("\n"):
        line = _clean(raw)
        m = _ROW.match(line)
        if not m:
            continue
        label = m.group(1).strip()
        if len(label) < 5 or label.startswith("+"):
            continue
        rows.append((label, m.group(2).split()))
    return rows


def _price(cell: str) -> float | None:
    raw = cell.replace(" ", "").replace(",", ".")
    if raw.lower().startswith("nd") or raw.startswith("-"):
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def fetch_mr_ansade_inpc_prices(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    session.verify = False
    resp = session.get(_API_URL, timeout=300)
    resp.raise_for_status()
    payload = resp.json()
    if not isinstance(payload, list):
        logger.warning("%s: unexpected payload shape from %s", _SOURCE_KEY, _API_URL)
        return None

    notes = []
    for pub in payload:
        names = [c.get("name", "") for c in (pub.get("categories") or [])]
        if not any("rix" in n for n in names):
            continue
        title = pub.get("title") or ""
        if "INPC" not in title and "Indice National" not in title:
            continue
        # The title month is read FIRST so a re-run can skip the download for
        # every month already on disk.
        month = _month_from(title, _TITLE_MONTH)
        if month is not None and month <= cutoff:
            continue
        notes.append((pub, month))

    if not notes:
        logger.info("%s: no INPC notes newer than %s", _SOURCE_KEY, cutoff)
        return None
    logger.info("%s: %d INPC note(s) to read", _SOURCE_KEY, len(notes))

    def text_of(entry):
        pub, month = entry
        text = (pub.get("pdf_content") or "").strip()
        if text:
            return pub, month, text
        f = pub.get("file") or {}
        url = f.get("url") if isinstance(f, dict) else None
        if not url:
            return pub, month, None
        try:
            import pdfplumber

            r = session.get(url, timeout=300)
            r.raise_for_status()
            with pdfplumber.open(io.BytesIO(r.content)) as pdf:
                return pub, month, "\n".join(p.extract_text() or "" for p in pdf.pages)
        except Exception:
            logger.warning("%s: could not read %s -- skipping", _SOURCE_KEY, url)
            return pub, month, None

    rows: list[dict] = []
    unknown: set[str] = set()
    undated = 0
    scrape_ts = get_scrape_ts()

    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        for pub, month, text in pool.map(text_of, notes):
            if not text or not _TABLE3.search(text):
                continue
            obs = _month_from(text, _CAPTION) or month
            if obs is None:
                undated += 1
                logger.warning(
                    "%s: no month in caption or title for %r -- skipping",
                    _SOURCE_KEY, (pub.get("title") or "")[:80],
                )
                continue
            if obs <= cutoff:
                continue
            f = pub.get("file") or {}
            url = f.get("url") if isinstance(f, dict) else _API_URL
            for label, values in _parse_table3(text):
                spec = _COICOP_MAP.get(_fold(label))
                if spec is None:
                    unknown.add(label)
                    continue
                item, unit, coicop = spec
                for centre, cell in zip(_CENTRES, values):
                    price = _price(cell)
                    if price is None:
                        continue
                    row = {
                        "observation_date": obs.isoformat(),
                        "period_kind": "monthly_avg",
                        "country": _COUNTRY,
                        "subnational_area": centre,
                        "source_key": _SOURCE_KEY,
                        "coicop_code": coicop,
                        "item_name": item,
                        "price_local": price,
                        "currency": _CURRENCY,
                        "unit": unit,
                        "source_url": url,
                        "notes": "average retail price at the INPC collection centre",
                        "scrape_ts": scrape_ts,
                        "observation_hash": None,
                    }
                    row["observation_hash"] = make_hash(row, _IDENT)
                    rows.append(row)

    if unknown:
        logger.warning(
            "%s: %d unmapped product label(s), not emitted: %s",
            _SOURCE_KEY, len(unknown), "; ".join(sorted(unknown)),
        )
    if undated:
        logger.warning("%s: %d note(s) skipped for an unreadable month", _SOURCE_KEY, undated)
    if not rows:
        return None
    df = pd.DataFrame(rows)
    before = len(df)
    df = df.drop_duplicates(subset="observation_hash", keep="first")
    if len(df) != before:
        logger.info("%s: dropped %d duplicate row(s)", _SOURCE_KEY, before - len(df))
    return df
