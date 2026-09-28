"""ENASA / INAC -- regulated airport passenger service fees, Sao Tome and Principe.

Resolucao n.o 36/2024 (Conselho de Ministros, approved 2024-10-16, published in the
Diario da Republica I Serie n.o 54 of 2024-10-25) sets the "Taxas de Seguranca e do
Desenvolvimento Aeroportuario" (TSDA, composed of the Taxa de Desenvolvimento
Aeronautico "E1" and the Taxa de Seguranca Aeroportuaria "CT") and the "Taxa de
Regulacao" (TR, code "NJ") charged to every departing/arriving air passenger at Sao
Tome and Principe's airports. This is a nationwide government-set fee schedule
(analytical_role: tariff), not a catalogue to crawl -- there is no live feed, so the
decision is hardcoded here, mirroring the ssa/west_africa/togo/csfppp_fuel_tariff.py
and ssa/west_africa/cote_divoire/dgh_fuel_tariff.py convention for regulator decrees
with no machine-readable primary feed.

Primary text verified live 2026-09-28 via a PDF of the official gazette page mirrored
at rstp.st (a national news outlet that reproduces Diario da Republica issues as
static PDFs under /wp-content/uploads/); ENASA's own site (enasa.st, reachable only
under curl_cffi's safari17_0/firefox133 impersonation profiles -- chrome124/chrome120
both 403) and the government portal's own gazette link (dre.gov.st, linked from
stp.gov.st/documentos) do not carry a copy: dre.gov.st does not resolve in DNS at all.
Update the source_url / re-verify content if rstp.st ever removes the file.

Fee amounts are set and published in EUROS (per Artigo 5), not in STN dobras -- the
decree itself denominates them in EUR, confirmed by reading the PDF text directly
("E62,00 (sessenta e dois Euros)" etc.), so currency=EUR here is a fact of the source,
not a conversion choice.

Six line items per Artigo 5 (three fee components x two flight categories):
  International, per leg: E1=EUR62.00, CT=EUR28.00, NJ=EUR20.00 (total EUR110.00)
  Domestic, per leg:       E1=EUR7.00,  CT=EUR4.00,  NJ=EUR5.00  (total EUR16.00)
Artigo 4(2) gives children aged 2-12 a flat 75% rate on "TSDA e TR" (i.e. all three
components) -- emitted here as six further rows rather than folded into the adult
rows, since it is a distinct, source-stated price point.

analytical_role: tariff -> PriceObservation.
coicop_classification: source_curated (coicop_codes: ["07.3.3"], passenger transport
by air -- these are compulsory per-passenger charges bundled into the air fare, not a
separate optional service).
period_kind: effective_from (dated regulatory instrument; effective_from =
publication date 2024-10-25, the entrada em vigor is not pinned to a later date in the
text).
"""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Sao Tome and Principe"
_CURRENCY = "EUR"
_SOURCE_KEY = "stp_enasa_airport_tariff"
_SOURCE_URL = (
    "https://rstp.st/wp-content/uploads/2024/11/"
    "Resolucao-n.36.2024-1_Taxas-de-aeroporto.pdf"
)
_COICOP = "07.3.3"
_IDENT = ["source_key", "observation_date", "item_name"]

# decision_date (publication date of the Diario da Republica issue carrying the
# resolucao) -> line items, per Resolucao n.o 36/2024, Artigo 5 and Artigo 4(2).
_KNOWN_DECISIONS: dict[str, list[dict]] = {
    "2024-10-25": [
        {
            "item_name": "TSDA E1 - Taxa de Desenvolvimento Aeronautico, voo internacional, adulto",
            "price_local": 62.00,
        },
        {
            "item_name": "TSDA CT - Taxa de Seguranca Aeroportuaria, voo internacional, adulto",
            "price_local": 28.00,
        },
        {
            "item_name": "TR NJ - Taxa de Regulacao, voo internacional, adulto",
            "price_local": 20.00,
        },
        {
            "item_name": "TSDA E1 - Taxa de Desenvolvimento Aeronautico, voo domestico, adulto",
            "price_local": 7.00,
        },
        {
            "item_name": "TSDA CT - Taxa de Seguranca Aeroportuaria, voo domestico, adulto",
            "price_local": 4.00,
        },
        {
            "item_name": "TR NJ - Taxa de Regulacao, voo domestico, adulto",
            "price_local": 5.00,
        },
        {
            "item_name": "TSDA E1 - Taxa de Desenvolvimento Aeronautico, voo internacional, crianca 2-12 anos (75%)",
            "price_local": round(62.00 * 0.75, 2),
        },
        {
            "item_name": "TSDA CT - Taxa de Seguranca Aeroportuaria, voo internacional, crianca 2-12 anos (75%)",
            "price_local": round(28.00 * 0.75, 2),
        },
        {
            "item_name": "TR NJ - Taxa de Regulacao, voo internacional, crianca 2-12 anos (75%)",
            "price_local": round(20.00 * 0.75, 2),
        },
        {
            "item_name": "TSDA E1 - Taxa de Desenvolvimento Aeronautico, voo domestico, crianca 2-12 anos (75%)",
            "price_local": round(7.00 * 0.75, 2),
        },
        {
            "item_name": "TSDA CT - Taxa de Seguranca Aeroportuaria, voo domestico, crianca 2-12 anos (75%)",
            "price_local": round(4.00 * 0.75, 2),
        },
        {
            "item_name": "TR NJ - Taxa de Regulacao, voo domestico, crianca 2-12 anos (75%)",
            "price_local": round(5.00 * 0.75, 2),
        },
    ],
}

# Airport-tax decrees are revised on the government's own irregular schedule (the
# previous update presstur.com reported was a ~300% hike, years apart) -- warn past
# roughly 2 years so a stale table doesn't silently ride along forever.
_STALE_AFTER_DAYS = 730


def _warn_if_stale(cutoff: date) -> None:
    latest = max(date.fromisoformat(d) for d in _KNOWN_DECISIONS)
    age = (cutoff - latest).days
    if age > _STALE_AFTER_DAYS:
        logger.warning(
            "[%s] _KNOWN_DECISIONS newest entry is %s, %d days before cutoff %s. "
            "Check the Diario da Republica / rstp.st for a newer Resolucao before "
            "trusting this series.",
            _SOURCE_KEY,
            latest.isoformat(),
            age,
            cutoff.isoformat(),
        )


def fetch_stp_enasa_airport_tariff(cutoff: date) -> pd.DataFrame | None:
    _warn_if_stale(cutoff)
    rows: list[dict] = []
    scrape_ts = get_scrape_ts()

    for decision_date_str, items in _KNOWN_DECISIONS.items():
        obs_date = date.fromisoformat(decision_date_str)
        if obs_date <= cutoff:
            continue
        for item in items:
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "effective_from",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": _COICOP,
                "item_name": item["item_name"],
                "price_local": float(item["price_local"]),
                "currency": _CURRENCY,
                "unit": "leg",
                "effective_from": obs_date.isoformat(),
                "source_url": _SOURCE_URL,
                "notes": (
                    "Resolucao n.o 36/2024 (Conselho de Ministros), Diario da "
                    "Republica I Serie n.o 54, 2024-10-25 -- TSDA (E1+CT) and TR "
                    "(NJ) airport passenger service fees, per leg. Denominated in "
                    "EUR by the decree itself, not STN."
                ),
                "scrape_ts": scrape_ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    if not rows:
        logger.info(
            "[%s] all decision dates <= cutoff %s -- nothing new", _SOURCE_KEY, cutoff
        )
        return None

    return pd.DataFrame(rows)
