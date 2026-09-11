"""Algeria -- "Mercuriale des prix des produits agricoles de large
consommation": the daily national retail price bulletin published jointly by
the Ministry of Agriculture (MADRP) and the Ministry of Internal Trade
(MCIRMN).

One PDF per publication day, a single page, bilingual French/Arabic, with a
national retail average plus the observed minimum and maximum for ~20-24
staple foods. The page's own footnote states the basis: "Moyenne nationale
observée dans les marchés de détail" -- retail markets, not wholesale.

DISCOVERY
---------
The landing page `madr.gov.dz/mercuriale-des-prix/` renders its list through
an Elementor JS template (`{{{data.link}}}`), so the PDF links are not in the
served HTML. The site is WordPress, and its REST media endpoint returns the
same files with dates attached:

    GET madr.gov.dz/wp-json/wp/v2/media?search=prix&per_page=100
        &_fields=id,date,source_url

Filenames are `prix_<DD>_<Month><YYYY>_MADRP-MCIRMN.pdf` with inconsistent
separators (`prix_10_Sept_2026_...` vs `prix_09_Sept2026_...`), so the
filename is NOT parsed for the date. The WordPress upload date is used only
to skip files older than the cutoff WITHOUT downloading them; the
authoritative observation date is read from the document's own
"date: 01 Juin 2026" line.

Measured 2026-09-11: the endpoint returns 47 mercuriale PDFs, 2026-06-01 to
2026-09-10 (page 2 is rejected, so this is the whole searchable set -- the
ministry does not expose an older archive through this route).

PARSING
-------
`pdfplumber` reads the text layer directly; no OCR needed on any issue
sampled. Some issues carry a SECOND page, "Mercuriale des prix ... des
grandes villes a l'Etranger" -- the same product labels priced in Paris,
Lyon, Lille, Marseille, Montreal, Rome and London and converted to DZD,
seven columns wide. Those are not Algerian prices and parsing them blind
emits a second "Tomate" at 887 DZD/kg against the domestic 80 under an
identical (observation_date, item_name) key, which `_IDENT` cannot tell
apart. Pages are therefore read in order and cut at that heading.

Each data line is

    [<group label>] <French product> <Moyenne> <Maximum> <Minimum> <Arabic>

and the group label is NOT reliably on its own line -- across issues the
extractor emits "Légumes frais" alone on one line but "Fruits frais Banane
575 601 549 ...", "Produits d'origine Poulet de chair ...", "animale Œufs
(Unité) ..." and even the footnote fragment "marchés de détail. Lait de vache
(Litre) ..." inline with a product. So the line is not split on position:
instead the longest `_COICOP_MAP` key occurring in the line is located, and
the three integers immediately following it are read. Lines that carry three
integers but match no key are logged so a new product cannot pass unnoticed.

COLUMN ORDER IS Moyenne, Maximum, Minimum -- average FIRST, not a min-max
pair. `price_local` is the Moyenne; min and max ride in `notes`. A row whose
three figures are not ordered Minimum <= Moyenne <= Maximum is dropped with
a warning rather than emitted: it means either the publisher mis-keyed the
row (2026-09-10 ships "Datte 507 375 384", which is internally impossible)
or the extractor read the columns in the wrong order, and the two are
indistinguishable from here. A missing row is recoverable; a wrong price is
not.

Units come from the label, because the header's "DA / Kg" does not hold for
every row: "Œufs (Unité)" is per egg and "Lait de vache (Litre)" per litre.

`_COICOP_MAP` stamps a per-ITEM COICOP-2018 leaf while the manifest stays
`coicop_classification: classifier` -- the same deliberate pairing as
stat_uz_avg_prices. `concatenate`'s `_build_classifier_csv_map` ingests a
fetcher's price_observations.csv ONLY for `classifier` sources, so declaring
`source_curated` would remove this file from the corpus altogether; the
per-row code instead rides through as `declared_coicop_codes` and
short-circuits the head in `classify` (`state=narrow_source`, confidence
1.0). Unmapped products are emitted uncoded (legitimate under `classifier`)
rather than dropped.

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

_MEDIA_API = "https://madr.gov.dz/wp-json/wp/v2/media"
_LANDING_URL = "https://madr.gov.dz/mercuriale-des-prix/"
_COUNTRY = "Algeria"
_CURRENCY = "DZD"
_SOURCE_KEY = "dz_madr_mercuriale"

_IDENT = ["source_key", "observation_date", "item_name"]

_PDF_NAME_RE = re.compile(r"/prix[_-]", re.I)
_DOC_DATE_RE = re.compile(
    r"date\s*:\s*(\d{1,2})\s+([A-Za-zéûÉÛ]+)\.?\s*(\d{4})", re.I
)
_FR_MONTHS = {
    "janvier": 1, "fevrier": 2, "février": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "aout": 8, "août": 8,
    "septembre": 9, "sept": 9, "octobre": 10, "novembre": 11,
    "decembre": 12, "décembre": 12,
}
_THREE_INTS_RE = re.compile(r"\b\d{1,6}\s+\d{1,6}\s+\d{1,6}\b")
# Heading of the foreign-cities annex table (see fetch_ for why it is cut).
_FOREIGN_RE = re.compile(r"grandes\s+villes\s+[aà]\s+l[’']\s*Etranger", re.I)

# French product label -> COICOP-2018 leaf.
_COICOP_MAP = {
    # Légumes frais
    "Pomme de terre": "01.1.7.5.1",
    "Tomate": "01.1.7.2.4",
    "Oignon sec": "01.1.7.4.3",
    "Ail sec": "01.1.7.4.2",
    "Ail vert": "01.1.7.4.2",
    "Carotte": "01.1.7.4.1",
    "Navet": "01.1.7.4.1",
    "Petit pois": "01.1.7.3.3",
    "Fève verte": "01.1.7.3.4",
    "Courgette": "01.1.7.2.5",
    "Haricot vert": "01.1.7.3.2",
    "Laitue": "01.1.7.1.4",
    "Poivron": "01.1.7.2.1",
    "Piment": "01.1.7.2.1",
    "Concombre": "01.1.7.2.2",
    "Aubergine": "01.1.7.2.3",
    "Courge": "01.1.7.2.5",
    "Salade": "01.1.7.1.4",
    # Fruits frais
    "Pomme locale": "01.1.6.3.1",
    "Datte": "01.1.6.1.3",
    "Raisin": "01.1.6.5.1",
    "Banane": "01.1.6.1.2",
    "Melon": "01.1.6.5.3",
    "Pastèque": "01.1.6.5.4",
    "Orange": "01.1.6.2.3",
    "Poire": "01.1.6.3.2",
    "Abricot": "01.1.6.3.3",
    "Pêche": "01.1.6.3.5",
    "Prune": "01.1.6.3.6",
    "Figue": "01.1.6.1.4",
    # Produits d'origine animale
    "Viande bovine locale": "01.1.2.2.1",
    "Viande ovine locale": "01.1.2.2.3",
    "Poulet de chair": "01.1.2.2.4",
    "Œufs (Unité)": "01.1.4.8.1",
    "Oeufs (Unité)": "01.1.4.8.1",
    "Lait de vache (Litre)": "01.1.4.1.1",
}

# Longest first, so "Pomme de terre" wins over "Pomme locale" on its own line
# and neither is matched by a shorter substring of the other.
_KEYS_BY_LENGTH = sorted(_COICOP_MAP, key=len, reverse=True)


def _doc_date(text: str) -> date | None:
    m = _DOC_DATE_RE.search(text)
    if not m:
        return None
    month = _FR_MONTHS.get(m.group(2).strip().lower().rstrip("."))
    if not month:
        return None
    try:
        return date(int(m.group(3)), month, int(m.group(1)))
    except ValueError:
        return None


def _unit_for(label: str) -> str:
    low = label.lower()
    if "unité" in low or "unite" in low:
        return "each"
    if "litre" in low:
        return "L"
    return "kg"  # the table header is "DA / Kg"


def _parse_lines(text: str) -> list[tuple[str, int, int, int]]:
    """(label, moyenne, maximum, minimum) per data line."""
    out: list[tuple[str, int, int, int]] = []
    for line in text.splitlines():
        label = None
        for key in _KEYS_BY_LENGTH:
            idx = line.find(key)
            if idx >= 0:
                label = key
                tail = line[idx + len(key):]
                break
        if label is None:
            if _THREE_INTS_RE.search(line) and re.search(r"[A-Za-zÀ-ÿ]{4}", line):
                logger.warning(
                    "%s: numeric line matched no product key: %r", _SOURCE_KEY, line.strip()
                )
            continue
        m = re.match(r"\s+(\d{1,6})\s+(\d{1,6})\s+(\d{1,6})\b", tail)
        if not m:
            continue
        out.append((label, int(m.group(1)), int(m.group(2)), int(m.group(3))))
    return out


def fetch_dz_madr_mercuriale(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(
        _MEDIA_API,
        params={"search": "prix", "per_page": 100, "_fields": "id,date,source_url"},
        timeout=90,
    )
    resp.raise_for_status()
    media = [
        m
        for m in resp.json()
        if str(m.get("source_url", "")).lower().endswith(".pdf")
        and _PDF_NAME_RE.search(str(m["source_url"]))
    ]
    if not media:
        logger.warning("%s: media endpoint returned no mercuriale PDFs", _SOURCE_KEY)
        return None

    import pdfplumber

    rows: list[dict] = []
    for entry in sorted(media, key=lambda m: m["date"]):
        # WordPress upload date: used ONLY to avoid downloading files that
        # cannot be newer than the cutoff. The authoritative date is the
        # document's own "date: <DD Month YYYY>" line, read below.
        try:
            uploaded = date.fromisoformat(str(entry["date"])[:10])
        except ValueError:
            uploaded = None
        if uploaded and uploaded < cutoff:
            continue

        url = entry["source_url"]
        pdf_resp = session.get(url, timeout=180)
        pdf_resp.raise_for_status()
        with pdfplumber.open(io.BytesIO(pdf_resp.content)) as pdf:
            pages = []
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                if _FOREIGN_RE.search(page_text):
                    # Some issues carry a SECOND table, "Mercuriale ... des
                    # grandes villes a l'Etranger": the same product labels
                    # priced in Paris/Lyon/Lille/Marseille/Montreal/Rome/
                    # London and converted to DZD, seven columns wide. Those
                    # are not Algerian prices, and parsed blind they emit a
                    # second "Tomate" at 887 DZD/kg against the domestic 80
                    # under an identical (date, item_name) key. Stop at that
                    # heading.
                    break
                pages.append(page_text)
            text = "\n".join(pages)
        if not text.strip():
            logger.warning("%s: no text layer in %s -- skipping", _SOURCE_KEY, url)
            continue

        obs_date = _doc_date(text)
        if obs_date is None:
            logger.warning("%s: no 'date:' line in %s -- skipping", _SOURCE_KEY, url)
            continue
        if obs_date <= cutoff:
            continue

        for label, moyenne, maximum, minimum in _parse_lines(text):
            if not (minimum <= moyenne <= maximum):
                logger.warning(
                    "%s: %s %s figures not ordered min<=moy<=max (%s/%s/%s) -- dropping",
                    _SOURCE_KEY,
                    obs_date.isoformat(),
                    label,
                    minimum,
                    moyenne,
                    maximum,
                )
                continue
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "snapshot",
                "country": _COUNTRY,
                "subnational_area": None,
                "source_key": _SOURCE_KEY,
                "coicop_code": _COICOP_MAP.get(label),
                "item_name": label,
                "price_local": float(moyenne),
                "currency": _CURRENCY,
                "unit": _unit_for(label),
                "source_url": url,
                "notes": "national retail average; min=%d; max=%d" % (minimum, maximum),
                "scrape_ts": get_scrape_ts(),
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    if not rows:
        return None
    df = pd.DataFrame(rows)
    # The ministry re-uploads a bulletin under a "-1" suffix from time to time
    # (prix_22_Juin_2026_MADRP-MCIRMN.pdf and ...-MCIRMN-1.pdf are the same
    # document, byte-for-byte identical figures). Both parse, both hash the
    # same, and the writer only de-duplicates the incoming frame against what
    # is already on disk -- not within the frame -- so the pair would ship as
    # two identical rows. De-duplicate on observation_hash here.
    before = len(df)
    df = df.drop_duplicates(subset="observation_hash", keep="first")
    if len(df) != before:
        logger.info(
            "%s: dropped %d re-uploaded duplicate row(s)", _SOURCE_KEY, before - len(df)
        )
    return df
