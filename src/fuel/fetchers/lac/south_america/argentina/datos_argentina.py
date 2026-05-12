"""Argentina Secretaría de Energía fuel prices fetcher.

Source: datos.gob.ar dataset "Precios en Surtidor - Resolución 314/2016"
  - Current CSV (small, ~35MB): all station-level reports for recent months
  - Historical CSV (~770MB): full history from 2016 onward

Strategy: aggregate to national monthly averages per product (Diurno rows only).
Pull current CSV always; pull historical only when cutoff is older than the
oldest month in the current CSV.
"""

from __future__ import annotations

import io
import logging
from datetime import date

import pandas as pd

from core.http import make_session

logger = logging.getLogger(__name__)

_CURRENT_CSV = (
    "http://datos.energia.gob.ar/dataset/1c181390-5045-475e-94dc-410429be4b17/"
    "resource/80ac25de-a44a-4445-9215-090cf55cfda5/download/"
    "precios-en-surtidor-resolucin-3142016.csv"
)
_HISTORICAL_CSV = (
    "http://datos.energia.gob.ar/dataset/1c181390-5045-475e-94dc-410429be4b17/"
    "resource/f8dda0d5-2a9f-4d34-b79b-4e63de3995df/download/"
    "precios-historicos.csv"
)

_COUNTRY = "Argentina"
_CURRENCY = "ARS"
_SOURCE_KEY = "ar_datos_argentina_monthly"
_UNIT_BY_PRODUCT = {
    "Nafta (súper) entre 92 y 95 Ron": "L",
    "Nafta (premium) de más de 95 Ron": "L",
    "Gas Oil Grado 2": "L",
    "Gas Oil Grado 3": "L",
    "GNC": "m3",
}


def _download_csv(session, url: str) -> bytes | None:
    try:
        resp = session.get(url, timeout=300)
        resp.raise_for_status()
        return resp.content
    except Exception:
        logger.exception("[ar_datos] Failed to download %s", url)
        return None


def _load_frame(raw: bytes) -> pd.DataFrame:
    df = pd.read_csv(
        io.BytesIO(raw),
        usecols=["indice_tiempo", "producto", "tipohorario", "precio"],
        dtype={
            "indice_tiempo": "string",
            "producto": "string",
            "tipohorario": "string",
        },
    )
    df = df[df["tipohorario"] == "Diurno"]
    df = df.dropna(subset=["indice_tiempo", "producto", "precio"])
    df["precio"] = pd.to_numeric(df["precio"], errors="coerce")
    df = df.dropna(subset=["precio"])
    df = df[df["producto"].isin(_UNIT_BY_PRODUCT)]
    return df


def _aggregate(df: pd.DataFrame, cutoff: date) -> list[dict]:
    grouped = (
        df.groupby(["indice_tiempo", "producto"], as_index=False)["precio"]
        .mean()
        .rename(columns={"precio": "price_local"})
    )

    rows: list[dict] = []
    for _, r in grouped.iterrows():
        ym = str(r["indice_tiempo"]).strip()
        try:
            year, month = ym.split("-")
            obs_date = date(int(year), int(month), 1)
        except (ValueError, AttributeError):
            continue
        if obs_date <= cutoff:
            continue
        product = str(r["producto"])
        rows.append(
            {
                "observation_date": obs_date.strftime("%Y-%m-%d"),
                "country": _COUNTRY,
                "fuel_product": product,
                "price_local": round(float(r["price_local"]), 4),
                "currency": _CURRENCY,
                "source_key": _SOURCE_KEY,
                "unit": _UNIT_BY_PRODUCT[product],
            }
        )
    return rows


def fetch_ar_datos_argentina(cutoff: date) -> pd.DataFrame | None:
    """Fetch Argentina retail fuel prices, aggregated to national monthly means."""
    session = make_session()

    current_raw = _download_csv(session, _CURRENT_CSV)
    if current_raw is None:
        return None
    current_df = _load_frame(current_raw)

    if current_df.empty:
        logger.info("[ar_datos] Current CSV empty after filtering")
        return None

    earliest_current = current_df["indice_tiempo"].min()
    try:
        earliest_y, earliest_m = str(earliest_current).split("-")
        earliest_date = date(int(earliest_y), int(earliest_m), 1)
    except (ValueError, AttributeError):
        earliest_date = date(1900, 1, 1)

    frames = [current_df]
    if cutoff < earliest_date:
        logger.info(
            "[ar_datos] cutoff %s < earliest current %s; pulling historical",
            cutoff,
            earliest_date,
        )
        hist_raw = _download_csv(session, _HISTORICAL_CSV)
        if hist_raw is not None:
            frames.append(_load_frame(hist_raw))

    combined = pd.concat(frames, ignore_index=True)
    rows = _aggregate(combined, cutoff)
    if not rows:
        logger.info("[ar_datos] No new rows after cutoff %s", cutoff)
        return None

    out = pd.DataFrame(rows).sort_values("observation_date").reset_index(drop=True)
    logger.info("[ar_datos] Returning %d rows (cutoff: %s)", len(out), cutoff)
    return out
