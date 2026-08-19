"""MAGA SIM (Guatemala) -- statutory monthly wholesale market price bulletin.

MAGA (Ministerio de Agricultura, Ganaderia y Alimentacion) runs the Sistema de
Informacion de Mercados (SIM, precios.maga.gob.gt), which publishes an
open-data monthly bulletin of wholesale prices across three national markets
(La Terminal, CENMA, 21 Calle -- all in/around Guatemala City) for ~160
agricultural products (produce, grains, meat, fish), 1998 to the current
month. This is the "MAGA (GT) publishes daily wholesale prices" statutory
class called out in the onboarding brief.

Distinct from the already-onboarded `wfp_gtm` shared fetcher: WFP Guatemala
(HDX) covers the same country/market-type (overlaps on La Terminal + CENMA,
same max observation month) but is a curated ~70-commodity subset; MAGA's own
open-data feed carries the full ~160-product catalog (more meat/fish/produce
detail) plus the "21 Calle" market WFP does not include. Kept as a separate
manifest rather than merged/dropped -- material incremental depth, not a
duplicate.

Gotcha for future maintainers: the open-data page
(otros/datos-abiertos/) publishes exactly ONE current bulletin download link
at a time, titled with the current month in Spanish (observed 2026-08-06:
"Precios mensuales de diversos productos agricolas en Guatemala a junio
2026 JSON.zip") -- filename changes every month, so the download URL must be
discovered from the page's href list (matched on the "JSON.zip" suffix), not
constructed. The zip contains a single JSON array of flat records; ~1.3% of
rows are exact byte-identical duplicates in the source itself (same market /
product / unit / date / null price) -- harmless, they collapse to the same
observation_hash.
"""

from __future__ import annotations

import io
import json
import logging
import re
import zipfile
from datetime import date, datetime

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_INDEX_URL = "https://precios.maga.gob.gt/otros/datos-abiertos/"
_ZIP_LINK_RE = re.compile(r'href=([^\s">]*JSON\.zip)', re.IGNORECASE)
_COUNTRY = "Guatemala"
_CURRENCY = "GTQ"
_SOURCE_KEY = "gt_maga_sim"

_IDENT = ["source_key", "observation_date", "Mercado", "Producto", "Medida"]


def _discover_zip_url(session) -> str | None:
    try:
        r = session.get(_INDEX_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        r.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] index page fetch failed: %s", _SOURCE_KEY, exc)
        return None
    m = _ZIP_LINK_RE.search(r.text)
    if not m:
        logger.warning("[%s] no *JSON.zip link found on open-data page", _SOURCE_KEY)
        return None
    href = m.group(1)
    return href if href.startswith("http") else f"https://precios.maga.gob.gt{href}"


def _parse_zip(zip_bytes: bytes, url: str, cutoff: date) -> list[dict]:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        json_names = [n for n in zf.namelist() if n.lower().endswith(".json")]
        if not json_names:
            logger.warning("[%s] zip has no .json member", _SOURCE_KEY)
            return []
        raw = zf.read(json_names[0])
    records = json.loads(raw.decode("utf-8"))

    ts = get_scrape_ts()
    rows: list[dict] = []
    for rec in records:
        precio_raw = rec.get("Precio")
        fecha_str = rec.get("Fecha")
        producto = rec.get("Producto")
        mercado = rec.get("Mercado")
        medida = rec.get("Medida")
        moneda = rec.get("Moneda") or _CURRENCY
        if precio_raw is None:
            continue
        try:
            # "Precio" is emitted as a string in the source JSON (e.g. "1000.00"),
            # not a number -- must be cast before the >0 sanity check.
            precio = float(precio_raw)
        except (TypeError, ValueError):
            continue
        if not (precio > 0):
            continue
        if not (fecha_str and producto and mercado):
            continue
        try:
            obs_date = datetime.strptime(fecha_str[:10], "%Y-%m-%d").date()
        except ValueError:
            continue
        if obs_date <= cutoff:
            continue
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "monthly_avg",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "Mercado": mercado,
            "Producto": producto,
            "Medida": medida,
            "item_name": producto,
            "price_local": round(float(precio), 4),
            "currency": moneda,
            "unit": medida,
            "source_url": url,
            "notes": f"mercado={mercado}; actor={rec.get('Actor')}",
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)
    return rows


def fetch_gt_maga_sim(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    zip_url = _discover_zip_url(session)
    if not zip_url:
        return None

    try:
        r = session.get(zip_url, timeout=60)
        r.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] zip fetch failed: %s", _SOURCE_KEY, exc)
        return None

    rows = _parse_zip(r.content, zip_url, cutoff)
    if not rows:
        return None

    df = pd.DataFrame(rows)
    # Drop the helper columns used only for hashing/notes -- not part of the
    # PRICE_COLUMNS writer schema (see writers.py; avoid the subnational_area
    # silent-drop-style trap by never emitting non-schema columns downstream).
    df = df.drop(columns=["Mercado", "Producto", "Medida"])
    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(df), cutoff)
    return df
