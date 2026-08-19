"""PROFECO "Quien es Quien en los Precios" (QQP) — Mexico's national comparative
price survey, published as half-month CSVs at
https://repodatos.atdt.gob.mx/api_update/profeco/programa_quien_es_quien_precios_{year}/{MM}-{year}_{HH}.csv
(HH = 01 for the first half of the month, 02 for the second). Each half-month
file is a raw per-store observation dump — tens to hundreds of thousands of
rows — across dozens of chains (Walmart/Bodega Aurrera, Soriana, Chedraui,
Comercial Mexicana, La Comer, ...) spanning food, groceries, and general
merchandise; COICOP is deferred to the downstream classifier/food-gate.

The dataset page (https://datos.profeco.gob.mx/datos_abiertos/qqp.php) only
advertises yearly RAR archives, but this CSV mirror was found live during
onboarding (HEAD/GET re-verified 2026-08-06: 10-2025_01.csv, 11-2025_01.csv,
11-2025_02.csv all 200; 12-2025_01.csv onward 503 — publish lag of several
months). Since there's no index/listing endpoint, availability is discovered
by walking (year, month, half) forward from the cutoff and HEAD-probing each
candidate URL, stopping after a run of consecutive misses past the last hit.
"""

from __future__ import annotations

import io
import logging
from datetime import date, datetime, timedelta, timezone

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_BASE = "https://repodatos.atdt.gob.mx/api_update/profeco"
_SOURCE_KEY = "mx_profeco_qqp"
_IDENT = ["source_key", "observation_date", "item_name", "price_local", "notes"]
_MAX_CONSECUTIVE_MISSES = 4
_MAX_PROBES = 60


def _csv_url(year: int, month: int, half: int) -> str:
    return f"{_BASE}/programa_quien_es_quien_precios_{year}/{month:02d}-{year}_{half:02d}.csv"


def _period_start(year: int, month: int, half: int) -> date:
    return date(year, month, 1 if half == 1 else 16)


def _next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def _candidate_periods(cutoff: date, horizon: date):
    year, month = cutoff.year, cutoff.month
    while True:
        period_start = date(year, month, 1)
        if period_start > horizon:
            return
        for half in (1, 2):
            start = _period_start(year, month, half)
            if start > cutoff:
                yield year, month, half, start
        year, month = _next_month(year, month)


def _discover_available(session, cutoff: date) -> list[tuple[int, int, int, str]]:
    today = datetime.now(timezone.utc).date()
    horizon = today + timedelta(days=45)
    found: list[tuple[int, int, int, str]] = []
    misses = 0
    probes = 0
    for year, month, half, start in _candidate_periods(cutoff, horizon):
        if start > today:
            break
        probes += 1
        if probes > _MAX_PROBES:
            break
        url = _csv_url(year, month, half)
        try:
            r = session.head(url, timeout=20, allow_redirects=True)
            ok = r.status_code == 200
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] HEAD failed for %s: %s", _SOURCE_KEY, url, exc)
            ok = False
        if ok:
            found.append((year, month, half, url))
            misses = 0
        else:
            misses += 1
            if found and misses >= _MAX_CONSECUTIVE_MISSES:
                break
    return found


def _rows_from_csv(text: str, url: str, cutoff: date) -> pd.DataFrame:
    df = pd.read_csv(io.StringIO(text), low_memory=False)
    df.columns = [c.strip().lower() for c in df.columns]
    required = {"producto", "presentacion", "marca", "precio", "fecha_registro"}
    if not required.issubset(df.columns):
        logger.warning(
            "[%s] unexpected columns in %s: %s", _SOURCE_KEY, url, list(df.columns)
        )
        return pd.DataFrame()

    df["precio"] = pd.to_numeric(df["precio"], errors="coerce")
    df["obs_date"] = pd.to_datetime(
        df["fecha_registro"], format="%Y/%m/%d", errors="coerce"
    ).dt.date
    df = df[df["precio"].notna() & (df["precio"] > 0) & df["obs_date"].notna()]
    df = df[df["obs_date"] > cutoff]
    if df.empty:
        return pd.DataFrame()

    for col in (
        "presentacion",
        "marca",
        "cadena_comercial",
        "giro",
        "nombre_comercial",
        "estado",
        "municipio",
    ):
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("")

    item_name = (
        (
            df["producto"].astype(str).str.strip()
            + " "
            + df["presentacion"].astype(str).str.strip()
            + " "
            + df["marca"].astype(str).str.strip()
        )
        .str.strip()
        .str.slice(0, 500)
    )

    notes = (
        df["cadena_comercial"].astype(str).str.strip()
        + "; "
        + df["giro"].astype(str).str.strip()
        + "; "
        + df["nombre_comercial"].astype(str).str.strip()
        + "; "
        + df["estado"].astype(str).str.strip()
        + ", "
        + df["municipio"].astype(str).str.strip()
    )

    ts = get_scrape_ts()
    out = pd.DataFrame(
        {
            "observation_date": df["obs_date"].astype(str),
            "period_kind": "daily",
            "country": "mexico",
            "source_key": _SOURCE_KEY,
            "item_name": item_name,
            "price_local": df["precio"].round(2),
            "currency": "MXN",
            "unit": df["presentacion"].astype(str).str.strip(),
            "source_url": url,
            "notes": notes,
            "scrape_ts": ts,
        }
    )
    out["observation_hash"] = out.apply(
        lambda row: make_hash(row.to_dict(), _IDENT), axis=1
    )
    return out


def fetch_mx_profeco_qqp(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    available = _discover_available(session, cutoff)
    if not available:
        logger.info(
            "[%s] no half-month files newer than cutoff=%s", _SOURCE_KEY, cutoff
        )
        return None

    frames: list[pd.DataFrame] = []
    for year, month, half, url in available:
        logger.info("[%s] downloading %s", _SOURCE_KEY, url)
        try:
            resp = session.get(url, timeout=180)
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] GET failed for %s: %s", _SOURCE_KEY, url, exc)
            continue
        resp.encoding = "utf-8-sig"
        rows = _rows_from_csv(resp.text, url, cutoff)
        if not rows.empty:
            frames.append(rows)
        logger.info("[%s] %s -> %d rows", _SOURCE_KEY, url, len(rows))

    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)
