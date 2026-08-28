"""IBGE SIDRA -- IPCA by COICOP-like group, chain-linked into an index level.

IBGE's SIDRA REST API (documented, machine-readable) publishes IPCA as a
monthly percent variation per group/subgroup/item (table 7060, Jan/2020
onward) -- it does NOT publish a number-index per group post-2020 (only the
national all-items headline carries a published number-index, table 1737,
which has no COICOP breakdown and is out of scope per the "headline CPI has
no coicop_code sentinel" note in the onboarding skill).

To emit a genuine IndexObservation (index_value, not a % change) per COICOP
division, this fetcher chain-links each group's published monthly %
variation into a synthetic index level, base 2020-01=100 -- the same
methodology IBGE itself uses to publish table 1737's headline number-index,
applied here per-group since IBGE does not publish that computation split by
group. This is disclosed in index_base_period on every row; it is NOT an
IBGE-published level series.

IBGE's own 9-group taxonomy does not map 1:1 onto COICOP 2018 13 divisions
(e.g. "Alimentacao e bebidas" folds food + alcoholic beverages together;
"Despesas pessoais" folds recreation + personal services + financial
services). Each group is mapped to its single nearest COICOP division;
divisions 02, 09, 11, 12 are not separately identifiable in IBGE's grouping
and are intentionally NOT emitted (same pattern as the SingStat COICOP
translation-map example in the onboarding skill).
"""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd
import requests

from prices.fetchers.utils import get_scrape_ts, make_hash

logger = logging.getLogger(__name__)

_METADATA_URL = "https://servicodados.ibge.gov.br/api/v3/agregados/7060/metadados"
_VALUES_URL = "https://servicodados.ibge.gov.br/api/v3/agregados/7060/periodos/{start}-{end}/variaveis/63"
_COUNTRY = "Brazil"
_SOURCE_KEY = "br_ibge_sidra_ipca"
_CLASSIFICACAO_ID = 315
_BASE_PERIOD_LABEL = (
    "2020-01=100 (chain-linked by this fetcher from IBGE's published monthly "
    "% variation, table 7060 -- NOT an IBGE-published index level)"
)
_START_PERIOD = "202001"

# IBGE IPCA top-level (nivel=1) group name prefix -> nearest single COICOP 2018
# division. Groups with no clean single-division match (recreation/tobacco/
# financial services folded into "Despesas pessoais"; alcohol folded into
# "Alimentacao e bebidas"; restaurants folded into "Alimentacao e bebidas")
# are approximated to the dominant division and flagged in code comments.
_GROUP_TO_COICOP = {
    "1.Alimentação e bebidas": "01",  # dominant: food; also carries alcohol + food-away-from-home
    "2.Habitação": "04",
    "3.Artigos de residência": "05",
    "4.Vestuário": "03",
    "5.Transportes": "07",
    "6.Saúde e cuidados pessoais": "06",  # dominant: health; also carries personal care (13)
    "7.Despesas pessoais": "13",  # catch-all: recreation/tobacco/financial services
    "8.Educação": "10",
    "9.Comunicação": "08",
}

_IDENT = ["source_key", "observation_date", "coicop_code"]


def _group_ids(session: requests.Session) -> dict[str, int]:
    r = session.get(_METADATA_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    r.raise_for_status()
    meta = r.json()
    cats = meta["classificacoes"][0]["categorias"]
    out: dict[str, int] = {}
    for c in cats:
        if c["nivel"] == 1 and c["nome"] in _GROUP_TO_COICOP:
            out[c["nome"]] = int(c["id"])
    return out


def _fetch_group_series(
    session: requests.Session, cat_id: int, end_period: str
) -> dict[str, float]:
    url = _VALUES_URL.format(start=_START_PERIOD, end=end_period)
    params = {
        "localidades": "N1[all]",
        "classificacao": f"{_CLASSIFICACAO_ID}[{cat_id}]",
    }
    r = session.get(
        url, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=30
    )
    r.raise_for_status()
    payload = r.json()
    if not payload:
        return {}
    resultados = payload[0].get("resultados", [])
    if not resultados:
        return {}
    series_list = resultados[0].get("series", [])
    if not series_list:
        return {}
    serie = series_list[0].get("serie", {})
    out: dict[str, float] = {}
    for period, val in serie.items():
        try:
            out[period] = float(val)
        except (TypeError, ValueError):
            continue  # ".." or missing -- IBGE not-yet-published marker
    return out


def _chain_index(pct_by_period: dict[str, float]) -> dict[str, float]:
    """Chain-link monthly % variations into an index level, base 100 at first period."""
    periods = sorted(pct_by_period)
    index: dict[str, float] = {}
    level = 100.0
    for i, period in enumerate(periods):
        if i > 0:
            pct = pct_by_period.get(period)
            if pct is not None:
                level = level * (1 + pct / 100.0)
            # else: carry level forward unchanged (missing month)
        index[period] = level
    return index


def fetch_br_ibge_sidra_ipca(cutoff: date) -> pd.DataFrame | None:
    session = requests.Session()
    today = date.today()
    end_period = f"{today.year:04d}{today.month:02d}"

    try:
        group_ids = _group_ids(session)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] metadata fetch failed: %s", _SOURCE_KEY, exc)
        return None
    if not group_ids:
        logger.warning("[%s] no matching COICOP groups found in metadata", _SOURCE_KEY)
        return None

    ts = get_scrape_ts()
    rows: list[dict] = []
    for group_name, cat_id in group_ids.items():
        coicop = _GROUP_TO_COICOP[group_name]
        try:
            pct_series = _fetch_group_series(session, cat_id, end_period)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[%s] series fetch failed for %r: %s", _SOURCE_KEY, group_name, exc
            )
            continue
        if not pct_series:
            continue
        index_series = _chain_index(pct_series)
        for period, level in index_series.items():
            year, month = int(period[:4]), int(period[4:6])
            obs_date = date(year, month, 1)
            if obs_date <= cutoff:
                continue
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "monthly_avg",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": coicop,
                "index_value": round(level, 4),
                "index_base_period": _BASE_PERIOD_LABEL,
                "source_url": "https://servicodados.ibge.gov.br/api/v3/agregados/7060",
                "notes": f"IBGE group: {group_name}",
                "scrape_ts": ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    if not rows:
        return None
    logger.info(
        "[%s] %d rows across %d COICOP divisions (cutoff=%s)",
        _SOURCE_KEY,
        len(rows),
        len(group_ids),
        cutoff,
    )
    return pd.DataFrame(rows)
