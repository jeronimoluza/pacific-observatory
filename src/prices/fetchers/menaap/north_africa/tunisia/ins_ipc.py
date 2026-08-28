"""Tunisia INS (Institut National de la Statistique) — Consumer Price Index, monthly.

INS (ins.tn) publishes a monthly CPI ("Indice des Prix a la Consommation") release as
a Drupal page at /publication/indice-des-prix-la-consommation-<french-month>-<year>,
linking a "Resultats definitifs IPC Base 2015" XLSX. Re-verified live 2026-08-07:
.../indice-des-prix-la-consommation-juillet-2026 -> 200, links
Resultats_definitifs_IPC_Base_2015_Juillet_2026.xlsx (4.1MB) -- genuinely current,
not a stale archive. Its "COICOP" sheet is a wide table: 66 named expenditure
categories (French labels) x weight (POND) x monthly index level, Jan 2015 (base
2015=100) through Jul 2026. Categories follow Tunisia's own COICOP-derived
12-division classification (pre-2018-revision, like Jordan's DOS CPI in this same
shard) -- division- and group-level detail, occasionally class-level for food.

Found via ins.tn's own homepage publication list (no dead ends this time -- unlike
the parallel Morocco/Tunisia commerce-ministry investigation, which found only
stale 2021 PDFs at commerce.gov.tn/upload/pdf/ -- noted here so that URL is not
re-investigated for this data).

Because each month's XLSX carries the full cumulative series back to Jan 2015 (not
just that month), this fetcher only needs to locate the single most recent
resolving month page (probing backward with unaccented French month slugs --
Drupal resolves both accented and unaccented URL forms) and melt its one sheet to
long form, rather than walking every month.

Two category labels ("Fournitures Scolaires", "Livres Scolaires") are dropped: their
COICOP home is ambiguous under strict division 10 semantics (school supplies/books
arguably belong under 09.5, but INS files them under "Enseignement"/division 10
without a clean group-level slot) and mapping them to any of the codes already used
by sibling rows would collide with the (source_key, observation_date, coicop_code)
identifying tuple. "Ensemble" (grand all-items total) is dropped -- no sanctioned
COICOP sentinel. One category label is transcribed exactly as it appears in the
source spreadsheet: "lectricité, gaz et autres combustibles" is missing its leading
"E" in INS's own file (verified against the raw XLSX bytes, not a decoding artifact
of this fetcher) -- kept verbatim so the lookup matches.

analytical_role: cpi_benchmark -> IndexObservation, not PriceObservation.
coicop_classification: publisher_labeled (French category labels -> COICOP, static
translation map, analogous to the BPS Indonesia / Jordan DOS CPI pattern).
coicop_divisions: 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Tunisia"
_SOURCE_KEY = "tn_ins_ipc"
_IDENT = ["source_key", "observation_date", "coicop_code"]
_BASE_PERIOD = "2015=100"
_MAX_MONTHS_BACK = 8
_MONTHS = [
    "janvier",
    "fevrier",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "aout",
    "septembre",
    "octobre",
    "novembre",
    "decembre",
]
_XLSX_RE = re.compile(r'href="([^"]*IPC[^"]*\.xlsx)"', re.IGNORECASE)

_COICOP_MAP = {
    "Produits alimentaires et boissons non alcoolisées": "01",
    "Produits alimentaires": "01.1",
    "Pain et céréales": "01.1.1",
    "Viandes": "01.1.2",
    "Poissons": "01.1.3",
    "Lait, fromage et œufs": "01.1.4",
    "Huiles alimentaires": "01.1.5",
    "Fruits": "01.1.6",
    "Légumes": "01.1.7",
    "Sucre, confiture, miel, chocolat et confiserie": "01.1.8",
    "Boissons non alcoolisées": "01.2",
    "Café, thé et cacao": "01.2.1",
    "Eaux minérales, boissons gazeuses et jus de fruits": "01.2.2",
    "Boissons alcoolisées et tabac": "02",
    "Boissons alcoolisées": "02.1",
    "Tabac": "02.2",
    "Articles d'habillement et chaussures": "03",
    "Articles d'habillement": "03.1",
    "Tissus pour habillement": "03.1.1",
    "Vêtements": "03.1.2",
    "Accessoires d'habillement": "03.1.3",
    "Chaussures": "03.2",
    "Logement, eau, gaz, électricité et autres combustibles": "04",
    "Loyers effectifs": "04.1",
    "Entretien et réparation des logements": "04.3",
    "Alimentation en eau et services divers liés au logement": "04.4",
    "lectricité, gaz et autres combustibles": "04.5",
    "Meubles, articles de ménage et entretien courant du foyer": "05",
    "Meubles, articles d'ameublement, tapis et autres revêtements de sol": "05.1",
    "Articles de ménage en textiles": "05.2",
    "Appareils ménagers": "05.3",
    "Verrerie, vaisselle et ustensiles de ménage": "05.4",
    "Outillage et autre matériel pour la maison et le jardin": "05.5",
    "Biens et services liés à l'entretien courant du foyer": "05.6",
    "Santé": "06",
    "Produits, appareils et matériels médicaux": "06.1",
    "Services ambulatoires": "06.2",
    "Services hospitaliers": "06.3",
    "Transports": "07",
    "Achat de véhicules": "07.1",
    "Dépenses d'utilisation des véhicules": "07.2",
    "Services de transport": "07.3",
    "Communications": "08",
    "Services postaux": "08.1",
    "Matériel de téléphonie": "08.2",
    "Services de téléphonie": "08.3",
    "Loisirs et culture": "09",
    "Matériel audiovisuel, photographique et de traitement de l'information": "09.1",
    "Autres biens durables à fonction récréative et culturelle": "09.2",
    "Autres articles et matériel de loisirs, de jardinage et animaux de compagnie": "09.3",
    "Services récréatifs et culturels": "09.4",
    "Journaux, livres et articles de papeterie": "09.5",
    "Enseignement": "10",
    "Enseignement préélémentaire et primaire": "10.1",
    "Enseignement secondaire": "10.2",
    "Enseignement non défini par niveau": "10.5",
    "Restaurants et hôtels": "11",
    "Restaurants et Cafés": "11.1",
    "Services d'hébergement": "11.2",
    "Biens et services divers": "12",
    "Soins personnels": "12.1",
    "Effets personnels": "12.3",
    "Assurance": "12.5",
    "Services financiers": "12.6",
}


def _candidate_pages(today: date) -> list[str]:
    out = []
    y, m = today.year, today.month
    for _ in range(_MAX_MONTHS_BACK):
        month_name = _MONTHS[m - 1]
        out.append(
            f"https://www.ins.tn/publication/indice-des-prix-la-consommation-{month_name}-{y}"
        )
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return out


def _find_latest_xlsx(session) -> str | None:
    for page_url in _candidate_pages(date.today()):
        try:
            r = session.get(page_url, timeout=30)
        except Exception as exc:  # noqa: BLE001
            logger.debug("[%s] page probe failed %s: %s", _SOURCE_KEY, page_url, exc)
            continue
        if r.status_code != 200:
            continue
        m = _XLSX_RE.search(r.text)
        if not m:
            continue
        return m.group(1)
    return None


def _rows_from_xlsx(xlsx_bytes: bytes, url: str, cutoff: date) -> list[dict]:
    df = pd.read_excel(io.BytesIO(xlsx_bytes), sheet_name="COICOP", header=None)
    header = df.iloc[6].tolist()
    date_cols = []
    for i, h in enumerate(header):
        if i < 2:
            continue
        ts = pd.to_datetime(h, errors="coerce")
        if pd.notna(ts):
            date_cols.append((i, ts.date()))
    if not date_cols:
        return []

    ts_scrape = get_scrape_ts()
    out: list[dict] = []
    for row_idx in range(7, len(df)):
        label = df.iloc[row_idx, 0]
        if pd.isna(label):
            continue
        label = str(label).strip()
        if label == "Ensemble":
            continue
        coicop = _COICOP_MAP.get(label)
        if coicop is None:
            logger.warning(
                "[%s] no COICOP mapping for %r — dropping row", _SOURCE_KEY, label
            )
            continue
        for col_idx, obs_date in date_cols:
            if obs_date <= cutoff:
                continue
            val = df.iloc[row_idx, col_idx]
            if pd.isna(val):
                continue
            try:
                index_value = float(val)
            except (TypeError, ValueError):
                continue
            r = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "monthly_avg",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": coicop,
                "index_value": round(index_value, 4),
                "index_base_period": _BASE_PERIOD,
                "source_url": url,
                "notes": f"category={label}",
                "scrape_ts": ts_scrape,
                "observation_hash": None,
            }
            r["observation_hash"] = make_hash(r, _IDENT)
            out.append(r)
    return out


def fetch_tn_ins_ipc(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    xlsx_url = _find_latest_xlsx(session)
    if not xlsx_url:
        logger.warning(
            "[%s] no IPC publication page resolved within lookback window", _SOURCE_KEY
        )
        return None
    try:
        resp = session.get(xlsx_url, timeout=60)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] xlsx fetch failed: %s", _SOURCE_KEY, exc)
        return None
    rows = _rows_from_xlsx(resp.content, xlsx_url, cutoff)
    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
