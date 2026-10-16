"""Peru Osinergmin SCOP per-station retail price register.

Source: the SCOP daily report "Registro de precios" for service stations,
grifos and gas stations (DMA-V-CCA-CCE), one record per station price change:

  https://www.osinergmin.gob.pe/seccion/centro_documental/hidrocarburos/
  SCOP/SCOP-DOCS/Reporte-Diario/CL-Registro-precios-DMA-V-CCA-CCE.csv

~1.5 GB, ';'-separated UTF-8, space-padded fixed-width fields, cumulative for
the current calendar year only (it restarts on 1 January). Columns: ID3;
ACTIVIDAD; REGISTRO DE HIDROCARBUROS (station code); RUC; RAZÓN SOCIAL;
DEPARTAMENTO; PROVINCIA; DISTRITO; DIRECCIÓN; FECHA DE REGISTRO
(YYYY/MM/DD HH:MM:SS.fff); PRODUCTO; PRECIO DE VENTA (SOLES, decimal comma);
UNIDAD (Galones). The server rejects requests without a browser User-Agent.

Strategy: download the whole file every run (the price in force at a month
end needs each station's earlier changes too, so a tail Range read is not
enough) as parallel 32 MB Range parts, parse each part keeping each
station's last change per product and month, carry it forward through later months of the year, and return one
row per station, product and month >= cutoff (the cutoff month is re-emitted
so a partial month is refreshed; unchanged rows dedup on hash). The build
turns stations into a national price (``station_aggregate`` in the YAML).
"""

from __future__ import annotations

import io
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pandas as pd

from core.http import make_session

logger = logging.getLogger(__name__)

URL = (
    "https://www.osinergmin.gob.pe/seccion/centro_documental/hidrocarburos/"
    "SCOP/SCOP-DOCS/Reporte-Diario/CL-Registro-precios-DMA-V-CCA-CCE.csv"
)
_COUNTRY = "Peru"
_CURRENCY = "PEN"
_SOURCE_KEY = "pe_osinergmin_scop_monthly"
_PRODUCTS = {"Diesel B5 S-50 UV", "GASOHOL REGULAR", "GASOHOL PREMIUM"}
# ACTIVIDAD, REGISTRO, DEPARTAMENTO, FECHA, PRODUCTO, PRECIO
_USECOLS = [1, 2, 5, 9, 10, 11]
_NAMES = ["act", "station", "dep", "ts", "product", "price"]
_PART = 32 * 1024 * 1024
_OVERSHOOT = 64 * 1024  # > one fixed-width line (~800 bytes)
_WORKERS = 8


def _reduce(chunk: pd.DataFrame) -> pd.DataFrame:
    """Retail rows of the mapped products -> last change per station/product/month."""
    for col in ("act", "product", "station", "dep", "ts"):
        chunk[col] = chunk[col].str.strip()
    chunk = chunk[
        chunk["product"].isin(_PRODUCTS)
        & ~chunk["act"].str.contains("MAYORISTA", na=True)
    ].copy()
    chunk["price"] = pd.to_numeric(
        chunk["price"].str.strip().str.replace(",", ".", regex=False), errors="coerce"
    )
    chunk = chunk[(chunk["price"] > 0) & chunk["station"].ne("")]
    chunk["month"] = chunk["ts"].str[:7]  # "YYYY/MM"; ts sorts as a string
    return (
        chunk.sort_values("ts")
        .groupby(["station", "product", "month"], as_index=False)
        .last()[["station", "product", "month", "ts", "dep", "price"]]
    )


def _get_range(session, first: int, last: int) -> bytes:
    for attempt in range(3):
        try:
            resp = session.get(
                URL, headers={"Range": f"bytes={first}-{last}"}, timeout=(30, 300)
            )
            resp.raise_for_status()
            if resp.status_code != 206:
                raise RuntimeError(f"Range not honoured (HTTP {resp.status_code})")
            return resp.content
        except Exception:
            if attempt == 2:
                raise
            logger.warning("[pe_osinergmin_scop] Retrying bytes %d-%d", first, last)
    raise AssertionError("unreachable")


def _parse_part(session, start: int, end: int, size: int) -> pd.DataFrame:
    """Lines that START in [start, end): read from start-1 and drop through the
    first newline, read past end to the newline that closes the last line."""
    lo = max(start - 1, 0)
    raw = _get_range(session, lo, min(end + _OVERSHOOT, size - 1))
    stop = raw.find(b"\n", end - 1 - lo)
    raw = raw if stop < 0 else raw[: stop + 1]
    if start > 0:
        raw = raw[raw.index(b"\n") + 1 :]
    chunk = pd.read_csv(
        io.BytesIO(raw),
        sep=";",
        header=None,
        usecols=_USECOLS,
        dtype=str,
        encoding="utf-8",
        encoding_errors="replace",
        on_bad_lines="skip",
    )
    chunk.columns = _NAMES
    return _reduce(chunk)


def _download() -> pd.DataFrame:
    """Parallel HTTP Range reads: one connection gets ~1-2 MB/s from this
    server (~25 min for the file), eight get ~8 MB/s."""
    session = make_session()
    head = session.get(URL, headers={"Range": "bytes=0-0"}, timeout=30)
    head.raise_for_status()
    size = int(head.headers["Content-Range"].rsplit("/", 1)[1])
    logger.info("[pe_osinergmin_scop] Downloading %.0f MB in ranges", size / 1e6)
    bounds = [(a, min(a + _PART, size)) for a in range(0, size, _PART)]
    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        parts = list(pool.map(lambda b: _parse_part(session, *b, size), bounds))
    df = pd.concat(parts, ignore_index=True)
    # A station/month can straddle two parts: keep its latest change.
    return (
        df.sort_values("ts")
        .groupby(["station", "product", "month"], as_index=False)
        .last()
    )


def _month_end_prices(df: pd.DataFrame) -> pd.DataFrame:
    """Price in force at each month end: carry each station's last change
    forward through the later months of the file (one calendar year)."""
    months = sorted(df["month"].unique())
    wide = df.pivot(index=["station", "product"], columns="month", values="price")
    wide = wide.reindex(columns=months).ffill(axis=1)
    out = wide.stack().rename("price").reset_index()
    dep = df.sort_values("ts").groupby("station")["dep"].last()
    out["dep"] = out["station"].map(dep)
    return out


def fetch_pe_osinergmin_scop(cutoff: date) -> pd.DataFrame | None:
    """Fetch Peru station-level retail prices from the Osinergmin SCOP register."""
    df = _download()
    if df.empty:
        logger.warning("[pe_osinergmin_scop] No station prices parsed")
        return None
    logger.info(
        "[pe_osinergmin_scop] %d station/product/month changes, %s..%s",
        len(df),
        df["month"].min(),
        df["month"].max(),
    )
    df = _month_end_prices(df)
    df["observation_date"] = df["month"].str.replace("/", "-") + "-01"
    df = df[df["observation_date"] >= cutoff.replace(day=1).isoformat()]
    if df.empty:
        logger.info("[pe_osinergmin_scop] No new rows after cutoff %s", cutoff)
        return None
    out = pd.DataFrame(
        {
            "observation_date": df["observation_date"],
            "country": _COUNTRY,
            "fuel_product": df["product"],
            "price_local": df["price"].astype(float).round(4),
            "currency": _CURRENCY,
            "source_key": _SOURCE_KEY,
            "unit": "gal",
            "subnational_area": df["dep"],
            "station": df["station"],
        }
    ).sort_values(["observation_date", "fuel_product", "station"])
    logger.info("[pe_osinergmin_scop] Returning %d rows (cutoff: %s)", len(out), cutoff)
    return out.reset_index(drop=True)
