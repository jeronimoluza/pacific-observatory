"""Lycee Francais de Djibouti (LFD) -- annual tuition and enrollment fee
schedule ("Reglement financier"), published as a PDF on the school's own
site.

Discovery: ddgs (yahoo backend) for "Djibouti universite scolarite frais
inscription" surfaced lfdjibouti.org/wp-content/uploads/2025/02/Reglement-
financier-2025-26.pdf directly. Verified live 2026-09-28: GET -> HTTP 200,
5-page PDF, text-native (not scanned -- pdfplumber.extract_text/extract_tables
both work with no OCR needed).

Two candidates probed the same institutional-education vertical and both were
dead ends: esig-djibouti.com/index.php/inscription/frais-de-scolarite/ is a
live 200 page but its fee section is still template placeholder text ("Lorem
et Lorem"), no real DJF figures anywhere in the HTML; univ.edu.dj (the public
Universite de Djibouti) publishes only an admissions-calendar announcement at
the page found, no fee table.

Page 2 (0-indexed page 1) carries a clean, ruled "Tarif annuel en DJF" table
-- parsed with `pdfplumber.extract_tables()` (NOT `extract_text()` + regex:
the raw text interleaves multiple 3-digit-grouped DJF amounts on one line
with no separator other than the same space used as the thousands
separator, e.g. "Collège 960 990 1 084 590 1 381 230" -- ambiguous by text
alone; the ruled-table extractor resolves it via the PDF's actual cell
geometry) -- 4 grade levels (Maternelle/Élémentaire/Collège/Lycée) x 3
nationality tiers (Français/Nationaux/Tiers) = 12 rows. The matching
"Payable en 3 fois" table on the same page is NOT parsed: its values are
exactly the annual figure divided by 3 (verified: 675165/3 == 225055 etc.),
so it is the same 12 prices in a different unit, not new information.

Also parsed: 2 flat admission fees from page 1 ("Droits de première
inscription" 150000 DJF, "Droits de réinscription" 60000 DJF) and 2 flat
international-section supplements from page 2 ("Frais scolaire
supplémentaires (SIA)" 100000 DJF, "Test d'entrée SIA" 10000 DJF) -- fixed
regexes against known label text, since this is a one-off institutional
document rather than a template scraped repeatedly across many pages.

Total 16 rows, verified live 2026-09-28.

"Reglement financier 2025-2026" -- treated as effective for the 2025-26
school year (2025-09-01). Re-runs against the same URL will re-fetch the
current year's PDF each cadence tick; if the school publishes a differently
named PDF for a later year, this fetcher's `_URL` constant needs updating
(not auto-discovered -- no index page was found listing prior years' PDFs).

COICOP: Maternelle/Élémentaire -> 10.1 (pre-primary and primary education).
Collège/Lycée -> 10.2 (secondary education). The four flat admin/SIA fees
are not grade-specific -> 10.6 (education services not definable by level).
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
import pdfplumber

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://lfdjibouti.org/wp-content/uploads/2025/02/Reglement-financier-2025-26.pdf"
_COUNTRY = "Djibouti"
_CURRENCY = "DJF"
_SOURCE_KEY = "lfd_tuition_dji"
_EFFECTIVE_FROM = "2025-09-01"

_GRADE_COICOP = {
    "Maternelle": "10.1",
    "Élémentaire": "10.1",
    "Collège": "10.2",
    "Lycée": "10.2",
}

_FLAT_FEE_PATTERNS = [
    ("Droits de première inscription", r"Droits de première inscription\s+([\d ]+?)\s*DJF"),
    ("Droits de réinscription", r"Droits de réinscription\s+([\d ]+?)\s*DJF"),
    ("Frais scolaire supplémentaires (SIA)", r"Frais scolaire supplémentaires \(SIA\)\s*:\s*([\d ]+?)\s*FDJ"),
    ("Test d'entrée SIA", r"Test d.entrée SIA\s*:\s*([\d ]+?)\s*FDJ"),
]

_IDENT = ["source_key", "effective_from", "item_name"]


def _parse_amount(s: str) -> float:
    return float(s.replace(" ", "").replace("\xa0", ""))


def fetch_lfd_tuition_dji(cutoff: date) -> pd.DataFrame | None:
    eff = date.fromisoformat(_EFFECTIVE_FROM)
    if eff <= cutoff:
        return None

    session = get_session()
    resp = session.get(_URL, timeout=30)
    resp.raise_for_status()

    ts = get_scrape_ts()
    rows: list[dict] = []

    import io

    with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
        full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)

        for label, pattern in _FLAT_FEE_PATTERNS:
            m = re.search(pattern, full_text)
            if not m:
                logger.warning("[%s] flat fee %r not found", _SOURCE_KEY, label)
                continue
            rows.append(
                {
                    "observation_date": _EFFECTIVE_FROM,
                    "period_kind": "effective_from",
                    "country": _COUNTRY,
                    "source_key": _SOURCE_KEY,
                    "item_name": f"LFD - {label}",
                    "price_local": _parse_amount(m.group(1)),
                    "currency": _CURRENCY,
                    "unit": "each",
                    "coicop_code": "10.6",
                    "effective_from": _EFFECTIVE_FROM,
                    "source_url": _URL,
                    "notes": "Reglement financier 2025-2026",
                    "scrape_ts": ts,
                    "observation_hash": None,
                }
            )

        tuition_table = None
        for page in pdf.pages:
            for table in page.extract_tables():
                header = [c.strip() for c in table[0] if c and c.strip()]
                if header[:1] == ["Tarif annuel en DJF"]:
                    tuition_table = table
                    break
            if tuition_table:
                break

        if tuition_table is None:
            logger.warning("[%s] tuition table not found", _SOURCE_KEY)
        else:
            for row in tuition_table[1:]:
                cells = [c.strip() for c in row if c and c.strip()]
                if len(cells) != 4 or cells[0] not in _GRADE_COICOP:
                    continue
                grade, fr, nat, tiers = cells
                for nationality, price_str in (
                    ("Français", fr),
                    ("Nationaux", nat),
                    ("Tiers", tiers),
                ):
                    rows.append(
                        {
                            "observation_date": _EFFECTIVE_FROM,
                            "period_kind": "effective_from",
                            "country": _COUNTRY,
                            "source_key": _SOURCE_KEY,
                            "item_name": f"LFD - {grade} - {nationality}",
                            "price_local": _parse_amount(price_str),
                            "currency": _CURRENCY,
                            "unit": "year",
                            "coicop_code": _GRADE_COICOP[grade],
                            "effective_from": _EFFECTIVE_FROM,
                            "source_url": _URL,
                            "notes": "Reglement financier 2025-2026; tarif annuel",
                            "scrape_ts": ts,
                            "observation_hash": None,
                        }
                    )

    if not rows:
        logger.warning("[%s] no rows parsed from %s", _SOURCE_KEY, _URL)
        return None

    for row in rows:
        row["observation_hash"] = make_hash(row, _IDENT)

    logger.info("[%s] %d rows from %s", _SOURCE_KEY, len(rows), _URL)
    return pd.DataFrame(rows)
