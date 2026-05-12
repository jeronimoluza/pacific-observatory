"""Brazil ANP weekly retail fuel price fetcher.

Source: ANP Sistema de Levantamento de Preços (weekly survey)
  - Three "ultimas 4 semanas" CSVs: gasolina-etanol, diesel-gnv, glp
  - Station-level observations with date of collection (DD/MM/YYYY)

Strategy: aggregate to national weekly means (week start = Monday of the
collection date). Historical backfill from monthly XLSX archives is not
implemented yet — first run pulls only the last 4 weeks.
"""

from __future__ import annotations

import io
import logging
from datetime import date, timedelta

import pandas as pd

from core.http import make_session

logger = logging.getLogger(__name__)

_BASE_URL = (
    "https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/"
    "arquivos/shpc/qus/ultimas-4-semanas-{slug}.csv"
)
_SLUGS = ("gasolina-etanol", "diesel-gnv", "glp")

_COUNTRY = "Brazil"
_CURRENCY = "BRL"
_SOURCE_KEY = "br_anp_weekly"

_UNIT_BY_PRODUCT = {
    "GASOLINA": "L",
    "GASOLINA ADITIVADA": "L",
    "ETANOL": "L",
    "DIESEL": "L",
    "DIESEL S10": "L",
    "GNV": "m3",
    "GLP": "cylinder",
}


def _download_csv(session, slug: str) -> pd.DataFrame | None:
    url = _BASE_URL.format(slug=slug)
    try:
        resp = session.get(url, timeout=60)
        resp.raise_for_status()
    except Exception:
        logger.exception("[br_anp] Failed to download %s", url)
        return None
    try:
        return pd.read_csv(
            io.BytesIO(resp.content),
            sep=";",
            encoding="utf-8-sig",
            usecols=["Produto", "Data da Coleta", "Valor de Venda"],
            dtype=str,
        )
    except Exception:
        logger.exception("[br_anp] Failed to parse %s", url)
        return None


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def fetch_br_anp(cutoff: date) -> pd.DataFrame | None:
    """Fetch Brazil ANP weekly retail fuel prices (last 4 weeks)."""
    session = make_session()

    frames: list[pd.DataFrame] = []
    for slug in _SLUGS:
        df = _download_csv(session, slug)
        if df is not None and not df.empty:
            frames.append(df)
    if not frames:
        return None

    df = pd.concat(frames, ignore_index=True)
    df = df.dropna(subset=["Produto", "Data da Coleta", "Valor de Venda"])
    df["Valor de Venda"] = (
        df["Valor de Venda"]
        .str.replace(",", ".", regex=False)
        .astype(float, errors="ignore")
    )
    df["Valor de Venda"] = pd.to_numeric(df["Valor de Venda"], errors="coerce")
    df = df.dropna(subset=["Valor de Venda"])

    df["coleta"] = pd.to_datetime(
        df["Data da Coleta"], format="%d/%m/%Y", errors="coerce"
    )
    df = df.dropna(subset=["coleta"])
    df["week_start"] = df["coleta"].dt.to_period("W-SUN").dt.start_time.dt.date

    grouped = (
        df.groupby(["week_start", "Produto"], as_index=False)["Valor de Venda"]
        .mean()
        .rename(columns={"Valor de Venda": "price_local", "Produto": "fuel_product"})
    )

    rows: list[dict] = []
    for _, r in grouped.iterrows():
        obs_date: date = r["week_start"]
        if obs_date <= cutoff:
            continue
        product = str(r["fuel_product"]).strip()
        unit = _UNIT_BY_PRODUCT.get(product)
        if unit is None:
            continue
        rows.append(
            {
                "observation_date": obs_date.strftime("%Y-%m-%d"),
                "country": _COUNTRY,
                "fuel_product": product,
                "price_local": round(float(r["price_local"]), 4),
                "currency": _CURRENCY,
                "source_key": _SOURCE_KEY,
                "unit": unit,
            }
        )

    if not rows:
        logger.info("[br_anp] No new rows after cutoff %s", cutoff)
        return None

    out = pd.DataFrame(rows).sort_values("observation_date").reset_index(drop=True)
    logger.info("[br_anp] Returning %d rows (cutoff: %s)", len(out), cutoff)
    return out
