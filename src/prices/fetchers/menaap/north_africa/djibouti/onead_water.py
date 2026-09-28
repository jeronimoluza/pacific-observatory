"""ONEAD (Office National de l'Eau et de l'Assainissement de Djibouti) --
regulated water/sanitation consumption tariff, Arrete n2014-738/PR/MAEPE-RH.

Discovery: onead.dj itself resolves to a bare Plesk default page (no real
site deployed -- confirmed 2026-09-28 with SSL verification disabled, title
"Maroc Cloud Plesk Hosting"). The tariff decree is instead published inline
as HTML (not a PDF) on the government gazette journalofficiel.dj, which
renders the full text of every "arrete"/"decret" as a normal page. No auth,
no WAF; a plain requests session works (verified live 2026-09-28).

The decree ("Date de Publication: 06/12/2014") sets a tiered per-m3 tariff
for three subscriber classes -- Domestique/Etat, Commercial, Industriel --
each with 7 consumption tranches (bimonthly billing) and two tariff columns:
"Tarif Eau seule" (water only) and "Tarif Eau et Assainissement" (water +
sewage collection bundled). Verified live 2026-09-28: 3 tables x 7 tranches
x 2 columns = 42 rows, all numeric, no blanks.

A fourth table ("Tarifs Speciaux par M3" -- port, private borehole, Cheikh
Osman standpipe, public fountains) is NOT parsed here: its water-only and
water+sanitation columns have differing blank-cell counts (sanitation is not
billed for several of those categories), so a positional label/value zip is
ambiguous without hand-auditing each row, and the category itself is mostly
bulk/institutional buyers rather than household consumption. Likewise the
one-off connection/meter-installation/meter-rental fee tables (by meter
diameter) are not parsed -- they are non-recurring capital charges, not a
recurring consumption price. Both are left for a future pass if revisited.

No newer arrete for this schedule was found in this pass (2026-09-28); the
2014 decree is treated as still in force. Emitted as a single
"effective_from" snapshot re-asserting the same observation_hash on re-run
until a newer decree supersedes it -- the fetcher does not attempt to detect
an update itself (the collect layer's cutoff comparison via observation_date
handles idempotence).

COICOP: "Eau seule" rows -> 04.4.1 (Water supply). "Eau et Assainissement"
rows -> 04.4.3 (Sewage collection), since the source itself bundles those
two components into a single administered rate.
"""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = (
    "https://www.journalofficiel.dj/texte-juridique/"
    "arrete-n2014-738-pr-maepe-rh-fixant-nouvelle-tarification-de-lonead-pour-"
    "la-vente-de-leau-et-la-collecte-de-lassainissement-liquide/"
)
_COUNTRY = "Djibouti"
_CURRENCY = "DJF"
_SOURCE_KEY = "onead_water_dji"
_EFFECTIVE_FROM = "2014-12-06"

_CLASSES = {
    "Tarifs Abonnés Domestiques et Etat par M3": "Domestique/Etat",
    "Tarifs Abonnés Commerciaux par M3": "Commercial",
    "Tarifs Abonnés Industriels par M3": "Industriel",
}

_IDENT = ["source_key", "effective_from", "item_name"]


def _cell_lines(cell) -> list[str]:
    return [ln.strip() for ln in cell.get_text("\n").split("\n") if ln.strip()]


def fetch_onead_water_dji(cutoff: date) -> pd.DataFrame | None:
    eff = date.fromisoformat(_EFFECTIVE_FROM)
    if eff <= cutoff:
        return None

    session = get_session()
    resp = session.get(_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    ts = get_scrape_ts()
    rows: list[dict] = []
    for table in soup.find_all("table"):
        trs = table.find_all("tr")
        if len(trs) < 3:
            continue
        header_cells = trs[0].find_all("td")
        if not header_cells:
            continue
        table_label = header_cells[0].get_text(strip=True)
        klass = _CLASSES.get(table_label)
        if klass is None:
            continue

        data_cells = trs[2].find_all("td")
        if len(data_cells) != 3:
            logger.warning(
                "[%s] unexpected cell count (%d) in %r table, skipping",
                _SOURCE_KEY,
                len(data_cells),
                table_label,
            )
            continue

        tranches = _cell_lines(data_cells[0])
        water_only = _cell_lines(data_cells[1])
        water_sani = _cell_lines(data_cells[2])
        if not (len(tranches) == len(water_only) == len(water_sani)):
            logger.warning(
                "[%s] misaligned columns in %r table (%d/%d/%d), skipping",
                _SOURCE_KEY,
                table_label,
                len(tranches),
                len(water_only),
                len(water_sani),
            )
            continue

        for tranche, wo, ws in zip(tranches, water_only, water_sani):
            for suffix, price_str, coicop in (
                ("Eau seule", wo, "04.4.1"),
                ("Eau et Assainissement", ws, "04.4.3"),
            ):
                try:
                    price = float(price_str.replace(",", "."))
                except ValueError:
                    continue
                row = {
                    "observation_date": _EFFECTIVE_FROM,
                    "period_kind": "effective_from",
                    "country": _COUNTRY,
                    "source_key": _SOURCE_KEY,
                    "item_name": f"ONEAD {klass} - {tranche} ({suffix})",
                    "price_local": price,
                    "currency": _CURRENCY,
                    "unit": "m3",
                    "coicop_code": coicop,
                    "effective_from": _EFFECTIVE_FROM,
                    "source_url": _URL,
                    "notes": "Arrete n2014-738/PR/MAEPE-RH; bimonthly consumption tranche",
                    "scrape_ts": ts,
                    "observation_hash": None,
                }
                row["observation_hash"] = make_hash(row, _IDENT)
                rows.append(row)

    if not rows:
        logger.warning("[%s] no rows parsed from %s", _SOURCE_KEY, _URL)
        return None

    logger.info("[%s] %d rows from %s", _SOURCE_KEY, len(rows), _URL)
    return pd.DataFrame(rows)
