"""Chile CNE "Bencina en Línea" fuel-price fetcher (SharePoint share).

Source: CNE publishes per-year bz2-compressed CSVs of every station-level
price-change event on a publicly shared OneDrive/SharePoint folder. Anonymous
access is granted via the share token — no API key required.

  Share URL: https://3b9x.short.gy/kp1HF1
  Resolves to: https://comisionenergia-my.sharepoint.com/:f:/g/personal/
               infoestadistica_cne_cl/EqpkvWFHBrdOh397XM-5YscBNZQd95t6qMDhiztydbVmLg

Files inside `bencina_en_linea/{YYYY}.csv.bz2` cover 2012-present. Each row is
a price-change event for one station, with columns:
  codigo, razon_social, distribuidor, direccion, latitud, longitud,
  nom_comuna, nom_region, combustible, precio, unidad_cobro, atencion,
  fecha_actualizacion (YYYY-MM-DD), hora_actualizacion, es_electrolinera,
  es_gasolinera.

Strategy: download every year file >= cutoff.year, aggregate to national
monthly means per product, return rows with observation_date > cutoff.
"""

from __future__ import annotations

import bz2
import io
import logging
import urllib.parse
from datetime import date

import pandas as pd

from core.http import make_session

logger = logging.getLogger(__name__)

_SHARE_URL = (
    "https://comisionenergia-my.sharepoint.com/:f:/g/personal/"
    "infoestadistica_cne_cl/EqpkvWFHBrdOh397XM-5YscBNZQd95t6qMDhiztydbVmLg"
)
_TENANT = "https://comisionenergia-my.sharepoint.com"
_FOLDER = (
    "/personal/infoestadistica_cne_cl/Documents/energia_abierta/"
    "catalogo_estadisticas/bencina_en_linea"
)
_LIST_URL = (
    f"{_TENANT}/personal/infoestadistica_cne_cl/_api/web/"
    f"GetFolderByServerRelativeUrl('{urllib.parse.quote(_FOLDER, safe='/')}')/Files"
)
_DOWNLOAD_URL = f"{_TENANT}/personal/infoestadistica_cne_cl/_layouts/15/download.aspx"

_COUNTRY = "Chile"
_CURRENCY = "CLP"
_SOURCE_KEY = "cl_cne_bencina_monthly"

_PRODUCT_UNITS = {
    "93": "L",
    "95": "L",
    "97": "L",
    "A93": "L",
    "A95": "L",
    "A97": "L",
    "DI": "L",
    "ADI": "L",
    "KE": "L",
    "AKE": "L",
    "GLP": "m3",
    "GNC": "m3",
}

# Pre-2023 files use long Spanish product names and `;` as separator.
# Map them onto the modern short codes so the YAML product map keeps working.
_LEGACY_PRODUCT_MAP = {
    "Gasolina 93": "93",
    "Gasolina 95": "95",
    "Gasolina 97": "97",
    "Petroleo Diesel": "DI",
    "Petróleo Diesel": "DI",
    "Kerosene": "KE",
    "GLP Vehicular": "GLP",
    "GNC": "GNC",
}


def _open_session():
    session = make_session()
    # Touch the share URL to populate FedAuth cookie for anonymous access.
    resp = session.get(_SHARE_URL, timeout=30)
    resp.raise_for_status()
    return session


def _list_year_files(session) -> list[str]:
    resp = session.get(
        _LIST_URL,
        params={"$select": "Name", "$orderby": "Name"},
        headers={"Accept": "application/json;odata=nometadata"},
        timeout=30,
    )
    resp.raise_for_status()
    names = [
        item.get("Name", "")
        for item in resp.json().get("value", [])
        if item.get("Name", "").endswith(".csv.bz2")
    ]
    return names


def _download_year(session, file_name: str) -> pd.DataFrame | None:
    source_url = f"{_FOLDER}/{file_name}"
    try:
        resp = session.get(_DOWNLOAD_URL, params={"SourceUrl": source_url}, timeout=180)
        resp.raise_for_status()
        raw = bz2.decompress(resp.content)
    except Exception:
        logger.exception("[cl_cne_bencina] Failed to download %s", file_name)
        return None

    # Sniff the separator from the header line. CSV layout changed in 2023:
    # pre-2023 files use `;` with long product names; 2023+ use `,` with codes.
    header_line = raw.split(b"\n", 1)[0].decode("utf-8", errors="replace")
    sep = ";" if header_line.count(";") > header_line.count(",") else ","

    try:
        df = pd.read_csv(
            io.BytesIO(raw),
            sep=sep,
            usecols=["combustible", "precio", "fecha_actualizacion"],
            dtype={"combustible": "string", "fecha_actualizacion": "string"},
        )
    except Exception:
        logger.exception("[cl_cne_bencina] Failed to parse %s", file_name)
        return None

    df["combustible"] = df["combustible"].replace(_LEGACY_PRODUCT_MAP)
    df["precio"] = pd.to_numeric(df["precio"], errors="coerce")
    df = df.dropna(subset=["combustible", "precio", "fecha_actualizacion"])
    df = df[df["combustible"].isin(_PRODUCT_UNITS)]
    return df


def fetch_cl_cne_bencina(cutoff: date) -> pd.DataFrame | None:
    """Fetch Chile CNE station-level prices from the public SharePoint share."""
    session = _open_session()

    file_names = _list_year_files(session)
    if not file_names:
        logger.warning("[cl_cne_bencina] No year files found")
        return None

    frames: list[pd.DataFrame] = []
    for name in file_names:
        try:
            year = int(name.split(".")[0])
        except ValueError:
            continue
        if year < cutoff.year:
            continue
        df = _download_year(session, name)
        if df is None or df.empty:
            continue
        frames.append(df)
        logger.info("[cl_cne_bencina] %s -> %d usable rows", name, len(df))

    if not frames:
        return None

    df = pd.concat(frames, ignore_index=True)
    fecha = pd.to_datetime(df["fecha_actualizacion"], errors="coerce")
    df = df.assign(fecha=fecha).dropna(subset=["fecha"])
    df["month"] = df["fecha"].dt.to_period("M").dt.to_timestamp().dt.date

    grouped = (
        df.groupby(["month", "combustible"], as_index=False)["precio"]
        .mean()
        .rename(columns={"precio": "price_local", "combustible": "fuel_product"})
    )

    rows: list[dict] = []
    for _, r in grouped.iterrows():
        obs_date: date = r["month"]
        if obs_date <= cutoff:
            continue
        product = str(r["fuel_product"])
        rows.append(
            {
                "observation_date": obs_date.strftime("%Y-%m-%d"),
                "country": _COUNTRY,
                "fuel_product": product,
                "price_local": round(float(r["price_local"]), 4),
                "currency": _CURRENCY,
                "source_key": _SOURCE_KEY,
                "unit": _PRODUCT_UNITS[product],
            }
        )

    if not rows:
        logger.info("[cl_cne_bencina] No new rows after cutoff %s", cutoff)
        return None

    out = (
        pd.DataFrame(rows)
        .sort_values(["observation_date", "fuel_product"])
        .reset_index(drop=True)
    )
    logger.info("[cl_cne_bencina] Returning %d rows (cutoff: %s)", len(out), cutoff)
    return out
