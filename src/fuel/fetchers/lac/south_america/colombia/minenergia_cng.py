"""Colombia MinEnergía CNG (GNCV) monthly average prices fetcher.

Source: datos.gov.co Socrata dataset he3q-86dn
  "Consulta Precios Promedio de Gas Natural Comprimido Vehicular (AUTOMATIZADO)"

Note: As of 2026-05, the equivalent automated datasets for gasoline and
diesel/ACPM are not available on datos.gov.co — the only currently-updated
MinEnergía price dataset is for CNG. Liquid-fuel prices need a separate
Tier 2 scraper (MinEnergía dashboard or Intégrame portal).

Strategy: aggregate station-level monthly observations to national monthly
mean per (year, month). Use Socrata SoQL aggregation server-side.
"""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd

from core.http import make_session

logger = logging.getLogger(__name__)

_API_URL = "https://www.datos.gov.co/resource/he3q-86dn.json"
_COUNTRY = "Colombia"
_CURRENCY = "COP"
_SOURCE_KEY = "co_minenergia_cng_monthly"


def fetch_co_minenergia_cng(cutoff: date) -> pd.DataFrame | None:
    """Fetch Colombia GNCV (CNG) monthly average prices via Socrata."""
    session = make_session()

    cutoff_str = cutoff.strftime("%Y-%m-%d")
    params = {
        "$select": (
            "anio_precio, mes_precio, tipo_combustible, "
            "avg(precio_promedio_publicado) as price_avg, count(*) as n"
        ),
        "$group": "anio_precio, mes_precio, tipo_combustible",
        "$where": f"fecha_precio > '{cutoff_str}'",
        "$order": "anio_precio, mes_precio",
        "$limit": 5000,
    }
    try:
        resp = session.get(_API_URL, params=params, timeout=60)
        resp.raise_for_status()
    except Exception:
        logger.exception("[co_minenergia_cng] Socrata request failed")
        return None

    data = resp.json()
    if not data:
        logger.info("[co_minenergia_cng] No new rows after cutoff %s", cutoff)
        return None

    rows: list[dict] = []
    for item in data:
        try:
            year = int(item["anio_precio"])
            month = int(item["mes_precio"])
            price = float(item["price_avg"])
        except (KeyError, TypeError, ValueError):
            continue
        try:
            obs_date = date(year, month, 1)
        except ValueError:
            continue
        if obs_date <= cutoff:
            continue
        rows.append(
            {
                "observation_date": obs_date.strftime("%Y-%m-%d"),
                "country": _COUNTRY,
                "fuel_product": str(item.get("tipo_combustible", "GNCV")),
                "price_local": round(price, 4),
                "currency": _CURRENCY,
                "source_key": _SOURCE_KEY,
                "unit": "m3",
            }
        )

    if not rows:
        return None

    out = pd.DataFrame(rows).sort_values("observation_date").reset_index(drop=True)
    logger.info("[co_minenergia_cng] Returning %d rows (cutoff: %s)", len(out), cutoff)
    return out
