"""ANEEL (Brazil) -- regulated per-distributor residential electricity tariff.

ANEEL (Agencia Nacional de Energia Eletrica) publishes a CKAN open-data portal
(dadosabertos.aneel.gov.br). The "Tarifas de aplicacao das distribuidoras de
energia eletrica" dataset carries one CSV with every homologated tariff order
for every distributor since 2010: TUSD (distribution-usage) and TE (energy)
components in R$/MWh, tagged by customer class/subclass/subgroup/modality and
an effective-date window (DatInicioVigencia/DatFimVigencia).

Re-verified live 2026-09-06: `known_blockers.md` had this CKAN instance
recorded as unreachable (curl exit 000, no TCP response at all) as of a
2026-08-07 probe. A plain `requests.get` on both the package_search API and
the CSV download now returns 200 -- the outage was transient on ANEEL's side,
not a WAF/bot block; no special TLS fingerprint or header was needed.

This fetcher filters the ~327k-row CSV down to the plain residential,
low-voltage, non-time-of-use tariff (DscClasse=Residencial,
DscSubGrupo=B1, DscSubClasse=Residencial, DscModalidadeTarifaria=Convencional,
DscBaseTarifaria="Tarifa de Aplicacao" [the tariff actually charged, not the
"Base Economica" reference figure], NomPostoTarifario/DscDetalhe="Nao se
aplica" [no peak/off-peak split]) -- 2,093 rows total across all distributors
and all years 2010-2026, small enough to emit in full rather than aggregate.
Price = (VlrTUSD + VlrTE) / 1000, converting R$/MWh to R$/kWh.

analytical_role: tariff -> PriceObservation.
coicop_classification: source_curated (coicop_codes: ["04.5.1"], electricity retail).
"""

from __future__ import annotations

import logging
from datetime import date
from io import BytesIO

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_CSV_URL = (
    "https://dadosabertos.aneel.gov.br/dataset/5a583f3e-1646-4f67-bf0f-69db4203e89e/"
    "resource/fcf2906c-7c32-4b9b-a637-054e7a5234f4/download/"
    "tarifas-homologadas-distribuidoras-energia-eletrica.csv"
)
_COUNTRY = "Brazil"
_CURRENCY = "BRL"
_SOURCE_KEY = "br_aneel_electricity_tariff"
_COICOP = "04.5.1.0"
_IDENT = ["source_key", "observation_date", "item_name"]

_FILTERS = {
    "DscClasse": "Residencial",
    "DscSubGrupo": "B1",
    "DscSubClasse": "Residencial",
    "DscModalidadeTarifaria": "Convencional",
    "DscBaseTarifaria": "Tarifa de Aplicação",
    "NomPostoTarifario": "Não se aplica",
    "DscDetalhe": "Não se aplica",
}


def _parse_brl(s: str) -> float | None:
    if not s:
        return None
    try:
        return float(str(s).strip().replace(".", "").replace(",", "."))
    except ValueError:
        return None


def fetch_br_aneel_electricity_tariff(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    try:
        resp = session.get(_CSV_URL, timeout=120)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] CSV fetch failed: %s", _SOURCE_KEY, exc)
        return None

    df = pd.read_csv(BytesIO(resp.content), sep=";", dtype=str, encoding="utf-8")
    for col, val in _FILTERS.items():
        df = df[df[col] == val]
    if df.empty:
        logger.warning("[%s] filter left 0 rows -- schema may have changed", _SOURCE_KEY)
        return None

    ts = get_scrape_ts()
    rows: list[dict] = []
    for rec in df.to_dict("records"):
        try:
            obs_date = pd.to_datetime(rec["DatInicioVigencia"]).date()
        except (ValueError, TypeError):
            continue
        if obs_date <= cutoff:
            continue
        tusd = _parse_brl(rec.get("VlrTUSD"))
        te = _parse_brl(rec.get("VlrTE"))
        if tusd is None or te is None:
            continue
        price_kwh = round((tusd + te) / 1000, 6)
        if price_kwh <= 0:
            continue
        distributor = (rec.get("SigAgente") or "").strip()
        if not distributor:
            continue
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "effective_from",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": f"{distributor} - Residencial B1 Convencional",
            "price_local": price_kwh,
            "currency": _CURRENCY,
            "unit": "kWh",
            "coicop_code": _COICOP,
            "source_url": _CSV_URL,
            "notes": (
                f"ANEEL homologated tariff order; distributor={distributor}; "
                f"TUSD={tusd} + TE={te} R$/MWh"
            ),
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    if not rows:
        return None
    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows)
