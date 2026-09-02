"""Burkina Faso ONEA — household water tariff schedule, effective-from snapshot.

ONEA (Office National de l'Eau et de l'Assainissement) publishes its tariff
schedule as a single-page PDF linked directly from the site's main nav
("Les tarifs" -> https://onea.bf/wp-content/uploads/2021/01/Tarifs-ONEA_2021.pdf).
Verified live 2026-09-01: 200, 133,072 bytes, one page, text extractable
(not scanned). No archive of prior tariff versions was found on the site —
this is the only live tariff document, so per the skill's tariff-schedule
guidance this fetcher snapshots the CURRENT schedule each run rather than
walking a history it cannot access.

The PDF is a two-column flyer; pdfplumber's linear text extraction keeps each
bullet's own line intact (label + dots + value on one row) but interleaves
rows from the two columns, so this fetcher matches each known label with its
own anchored regex rather than attempting a single generic table parse —
safer against the layout jumble, and it fails loudly (returns None, logs a
warning naming which anchors were not found) rather than silently emitting a
partial/stale schedule if ONEA changes the wording.

Only the household ("tarifs ménage") block is emitted as COICOP-coded rows;
the "sociétés" (business/institutional) block and VAT lines are commercial /
tax rows out of scope for a household PPP basket and are not emitted.

CURRENCY: XOF, no minor unit — "1 104 FCFA/m3" is 1,104 XOF, not 11.04.

coicop_classification: source_curated -- COICOP 04.4.1 (water supply) for the
consumption tiers and the subscriber service charge; 04.4.2 (sewage
collection) for the two "assainissement" (sanitation) redevances.
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Burkina Faso"
_SOURCE_KEY = "onea_water_tariff_bfa"
_PDF_URL = "https://onea.bf/wp-content/uploads/2021/01/Tarifs-ONEA_2021.pdf"
_SOURCE_PAGE = "https://onea.bf/services/service-en-eau-potable/"
_EFFECTIVE_FROM = date(2021, 1, 1)
_IDENT = ["source_key", "observation_date", "item_name"]

# (item_name, unit, coicop_code, regex matching "<label> ... <value> FCFA[/unit]")
_ANCHORS: list[tuple[str, str, str, re.Pattern]] = [
    (
        "Eau potable — tranche 0 à 8 m3 (tarif ménage)",
        "m3",
        "04.4.1",
        re.compile(r"Tranche de 0 à 8 m3[\s.…]*?(\d[\d\s]*)\s*FCFA"),
    ),
    (
        "Eau potable — tranche 9 à 15 m3 (tarif ménage)",
        "m3",
        "04.4.1",
        re.compile(r"Tranche de 9 m3 à 15 m3[\s.…]*?(\d[\d\s]*)\s*FCFA"),
    ),
    (
        "Eau potable — tranche 16 à 25 m3 (tarif ménage)",
        "m3",
        "04.4.1",
        re.compile(r"Tranche de 16 m3 à 25 m3[\s.…]*?(\d[\d\s]*)\s*FCFA"),
    ),
    (
        "Eau potable — tranche plus de 25 m3 (tarif ménage)",
        "m3",
        "04.4.1",
        re.compile(r"Tranche de plus de 25 m3[\s.…]*?(\d[\d\s]*)\s*FCFA"),
    ),
    (
        "Redevance service des abonnés (ménage)",
        "facture",
        "04.4.1",
        re.compile(r"Redevance service des abonnés[\s.…]*?(\d[\d\s]*)\s*FCFA"),
    ),
    (
        "Redevance assainissement autonome (ménage)",
        "m3",
        "04.4.2",
        re.compile(r"Redevance assainissement autonome[\s.…]*?(\d[\d\s]*)\s*FCFA"),
    ),
    (
        "Redevance assainissement collectif (ménage)",
        "m3",
        "04.4.2",
        re.compile(r"Redevance assainissement collectif[\s.…]*?(\d[\d\s]*)\s*FCFA"),
    ),
    (
        "Eau — borne fontaine (seau 20 litres)",
        "unit",
        "04.4.1",
        re.compile(r"seau de 20 litres[\s.…]*?(\d[\d\s]*)\s*FCFA"),
    ),
    (
        "Eau — borne fontaine (bassine 40 litres)",
        "unit",
        "04.4.1",
        re.compile(r"bassine de 40 litres[\s.…]*?(\d[\d\s]*)\s*FCFA"),
    ),
    (
        "Eau — borne fontaine (fût 220 litres)",
        "unit",
        "04.4.1",
        re.compile(r"fût de 220 litres[\s.…]*?(\d[\d\s]*)\s*FCFA"),
    ),
]


def _parse_xof(raw: str) -> float | None:
    digits = re.sub(r"[^\d]", "", raw)
    if not digits:
        return None
    return float(digits)


def fetch_onea_water_tariff_bfa(cutoff: date) -> pd.DataFrame | None:
    if _EFFECTIVE_FROM <= cutoff:
        logger.info("[%s] no new release past cutoff=%s", _SOURCE_KEY, cutoff)
        return None

    session = get_session()
    try:
        resp = session.get(_PDF_URL, timeout=60)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] PDF fetch failed: %s", _SOURCE_KEY, exc)
        return None

    import pdfplumber
    from io import BytesIO

    try:
        with pdfplumber.open(BytesIO(resp.content)) as pdf:
            text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] PDF parse failed: %s", _SOURCE_KEY, exc)
        return None

    ts = get_scrape_ts()
    rows: list[dict] = []
    missing: list[str] = []
    for item_name, unit, coicop_code, pattern in _ANCHORS:
        m = pattern.search(text)
        if not m:
            missing.append(item_name)
            continue
        price = _parse_xof(m.group(1))
        if price is None or price <= 0:
            missing.append(item_name)
            continue
        row = {
            "observation_date": _EFFECTIVE_FROM.isoformat(),
            "period_kind": "effective_from",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": coicop_code,
            "item_name": item_name,
            "price_local": price,
            "currency": "XOF",
            "unit": unit,
            "source_url": _PDF_URL,
            "notes": "ONEA household water/sanitation tariff schedule (flyer, no dated versions archived)",
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    if missing:
        logger.warning("[%s] anchors not matched: %s", _SOURCE_KEY, missing)
    if not rows:
        return None

    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows)
