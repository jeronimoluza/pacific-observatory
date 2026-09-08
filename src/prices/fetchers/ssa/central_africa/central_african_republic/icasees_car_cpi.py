"""Central African Republic — ICASEES national CPI (IHPC), by COICOP division.

ICASEES (Institut Centrafricain des Statistiques et des Études Économiques
et Sociales), the national statistics office, publishes a monthly IHPC
(Indice Harmonisé des Prix à la Consommation) workbook as a plain, keyless
XLSX download from its Joomla/edocman document library:

  https://www.icasees.org/index.php/component/edocman/
    indice-des-prix-a-la-consommation-ihpc-mensuel-de-2015-2026/download

Verified live 2026-09-06: a 4-sheet workbook (`Données`, `Métadonnées`,
`Notes_Methodologiques`, `Archive_Base1981_Brute`). The `Données` sheet is
wide: one row per series code (IND1..IND14), one column per month
(`2015M1`..`2026M4`, 136 months at probe time). IND1 = all-items headline
(dropped -- no sanctioned COICOP sentinel in this pipeline, see the skill's
open design question); IND2..IND13 map 1:1 to the 12 COICOP-1999-style
divisions in the exact order ICASEES's own `Métadonnées` sheet documents
(`_COICOP_MAP` below, keyed off the `Indicateur` column, not just row
position, so a reordered future release doesn't silently mis-map); IND14 =
year-on-year inflation rate (%), not an index level -- dropped.

Per ICASEES's own `Notes_Methodologiques` sheet, the series underwent a base
change in January 2020 (old base ~1981, new base ~2019); ICASEES's published
bulletins carry an official reconciliation coefficient (4.12919) which this
specific workbook has already applied to the pre-2020 cells so the full
2015-2026 series sits on one consistent base (`2019=100`) -- confirmed by
their own worked check (Dec-2019 old-base 412.10 / 4.12919 = 99.78, matching
Jan-2020 new-base 99.14). The unreconciled 1981-base originals are preserved
separately in the `Archive_Base1981_Brute` sheet, not used here.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from io import BytesIO

import pandas as pd
from curl_cffi import requests as curl_requests

from prices.fetchers.utils import get_scrape_ts, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Central African Republic"
_SOURCE_KEY = "icasees_car_cpi"
_SOURCE_URL = (
    "https://www.icasees.org/index.php/component/edocman/"
    "indice-des-prix-a-la-consommation-ihpc-mensuel-de-2015-2026/download"
    "?Itemid=0"
)
_INDEX_BASE = "2019=100"
_IDENT = ["source_key", "observation_date", "coicop_code"]

# ICASEES "Indicateur" label (Métadonnées sheet) -> COICOP-2018 2-digit
# division. IND1 (INDICE GLOBAL, headline) and IND14 (Inflation, a rate not
# a level) are intentionally absent -- both dropped.
_COICOP_MAP = {
    "Produits alimentaires et boissons non alcoolisées": "01",
    "Boissons alcoolisées et tabac": "02",
    "Articles d'habillement et chaussures": "03",
    "Logement, eau, gaz, électricité et autres combustibles": "04",
    "Meubles, articles de ménage et entretien courant de la maison": "05",
    "Santé": "06",
    "Transports": "07",
    "Communications": "08",
    "Loisirs et culture": "09",
    "Enseignement": "10",
    "Restaurants et hôtels": "11",
    "Biens et services divers": "12",
}

_PERIOD_RE = re.compile(r"^(\d{4})M(\d{1,2})$")


def fetch_icasees_car_cpi(cutoff: date) -> pd.DataFrame | None:
    resp = curl_requests.get(_SOURCE_URL, impersonate="chrome124", timeout=30)
    resp.raise_for_status()

    xls = pd.ExcelFile(BytesIO(resp.content))
    meta = pd.read_excel(xls, sheet_name="Métadonnées")
    data = pd.read_excel(xls, sheet_name="Données")

    code_to_coicop = {}
    for _, r in meta.iterrows():
        indicateur = str(r.get("Indicateur", "")).strip()
        coicop = _COICOP_MAP.get(indicateur)
        if coicop:
            code_to_coicop[str(r["Code"]).strip()] = coicop

    if not code_to_coicop:
        logger.warning("[%s] no IND codes matched _COICOP_MAP", _SOURCE_KEY)
        return None

    period_cols = [c for c in data.columns if _PERIOD_RE.match(str(c))]
    scrape_ts = get_scrape_ts()
    rows: list[dict] = []

    for _, r in data.iterrows():
        code = str(r.get("Code", "")).strip()
        coicop = code_to_coicop.get(code)
        if not coicop:
            continue  # IND1 (headline) and IND14 (inflation rate) land here
        for col in period_cols:
            m = _PERIOD_RE.match(str(col))
            year, month = int(m.group(1)), int(m.group(2))
            try:
                obs_date = date(year, month, 1)
            except ValueError:
                continue
            if obs_date <= cutoff:
                continue
            raw = r.get(col)
            if raw is None or (isinstance(raw, float) and pd.isna(raw)):
                continue
            try:
                index_value = float(raw)
            except (TypeError, ValueError):
                continue

            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "monthly_avg",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": coicop,
                "index_value": index_value,
                "index_base_period": _INDEX_BASE,
                "source_url": _SOURCE_URL,
                "notes": f"ICASEES IHPC, {code}.",
                "scrape_ts": scrape_ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    if not rows:
        logger.info(
            "[%s] all observation dates <= cutoff %s -- nothing new",
            _SOURCE_KEY,
            cutoff,
        )
        return None

    return pd.DataFrame(rows)
