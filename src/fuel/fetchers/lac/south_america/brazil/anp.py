"""Brazil ANP weekly national retail fuel price fetcher.

Source: ANP Série Histórica do Levantamento de Preços (SHLP) — national-level
weekly XLSX files published by Superintendência de Defesa da Concorrência.

  https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/
    precos/precos-revenda-e-de-distribuicao-combustiveis/
    serie-historica-do-levantamento-de-precos

Two files cover the full series:
  - semanal-brasil-2004-a-2012.xlsx (header row 12, products w/ accent)
  - semanal-brasil-desde-2013.xlsx  (header row 17, accents dropped, +DIESEL S10)

We use PREÇO MÉDIO REVENDA (national mean retail). ANP does not publish a
weekly median — only mean, stdev, min, max.
"""

from __future__ import annotations

import io
import logging
from datetime import date, datetime

import pandas as pd

from core.http import make_session

logger = logging.getLogger(__name__)

_BASE = (
    "https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/"
    "precos/precos-revenda-e-de-distribuicao-combustiveis/shlp"
)
_URL_HISTORICAL = f"{_BASE}/2001-2012/semanal-brasil-2004-a-2012.xlsx"
_URL_CURRENT = f"{_BASE}/semanal/semanal-brasil-desde-2013.xlsx"
_HISTORICAL_END = date(2012, 12, 31)

_COUNTRY = "Brazil"
_CURRENCY = "BRL"
_SOURCE_KEY = "br_anp_weekly"

_UNIT_MAP = {
    "R$/L": "L",
    "R$/13KG": "cylinder",
    "R$/M3": "m3",
}

_PRODUCT_RENAME = {
    "ÓLEO DIESEL": "OLEO DIESEL",
}


def _download_xlsx(session, url: str) -> bytes | None:
    try:
        resp = session.get(url, timeout=120)
        resp.raise_for_status()
        return resp.content
    except Exception:
        logger.exception("[br_anp] Failed to download %s", url)
        return None


def _find_header_row(blob: bytes) -> int:
    """Locate the row containing 'DATA INICIAL' — header offset varies by file."""
    probe = pd.read_excel(io.BytesIO(blob), header=None, nrows=30, usecols=[0])
    for idx, val in enumerate(probe[0].astype(str)):
        if val.strip().upper() == "DATA INICIAL":
            return idx
    raise ValueError("[br_anp] DATA INICIAL header not found in first 30 rows")


def _parse(blob: bytes) -> pd.DataFrame:
    header = _find_header_row(blob)
    df = pd.read_excel(io.BytesIO(blob), header=header)
    df.columns = [str(c).strip() for c in df.columns]
    df = df.rename(
        columns={
            "DATA INICIAL": "data_inicial",
            "PRODUTO": "produto",
            "UNIDADE DE MEDIDA": "unidade",
            "PREÇO MÉDIO REVENDA": "preco_medio",
        }
    )
    df = df[["data_inicial", "produto", "unidade", "preco_medio"]].copy()
    df = df.dropna(subset=["data_inicial", "produto", "preco_medio"])
    df["data_inicial"] = pd.to_datetime(df["data_inicial"], errors="coerce")
    df = df.dropna(subset=["data_inicial"])
    df["preco_medio"] = pd.to_numeric(df["preco_medio"], errors="coerce")
    df = df.dropna(subset=["preco_medio"])
    df["produto"] = df["produto"].astype(str).str.strip().str.upper()
    df["produto"] = df["produto"].replace(_PRODUCT_RENAME)
    df["unidade"] = (
        df["unidade"].astype(str).str.strip().str.upper().str.replace("³", "3")
    )
    return df


def fetch_br_anp(cutoff: date) -> pd.DataFrame | None:
    """Fetch Brazil ANP weekly national mean retail prices.

    Always pulls the 2013+ file; pulls the 2004-2012 file only when the cutoff
    predates 2013 (typically only on a full backfill).
    """
    session = make_session()

    blobs: list[bytes] = []
    if cutoff < _HISTORICAL_END:
        b = _download_xlsx(session, _URL_HISTORICAL)
        if b is not None:
            blobs.append(b)
    b = _download_xlsx(session, _URL_CURRENT)
    if b is not None:
        blobs.append(b)
    if not blobs:
        return None

    frames = [_parse(blob) for blob in blobs]
    df = pd.concat(frames, ignore_index=True)

    cutoff_ts = pd.Timestamp(cutoff)
    df = df[df["data_inicial"] > cutoff_ts]
    if df.empty:
        logger.info("[br_anp] No new rows after cutoff %s", cutoff)
        return None

    today_ts = pd.Timestamp(datetime.utcnow().date())
    bad = df["data_inicial"] > today_ts
    if bad.any():
        logger.warning("[br_anp] Dropping %d rows dated in the future", int(bad.sum()))
        df = df[~bad]
        if df.empty:
            return None

    rows: list[dict] = []
    for _, r in df.iterrows():
        unit = _UNIT_MAP.get(r["unidade"])
        if unit is None:
            logger.debug("[br_anp] Unknown unit %r — skipping row", r["unidade"])
            continue
        rows.append(
            {
                "observation_date": r["data_inicial"].date().strftime("%Y-%m-%d"),
                "country": _COUNTRY,
                "fuel_product": r["produto"],
                "price_local": round(float(r["preco_medio"]), 4),
                "currency": _CURRENCY,
                "source_key": _SOURCE_KEY,
                "unit": unit,
            }
        )

    if not rows:
        return None

    out = (
        pd.DataFrame(rows)
        .sort_values(["observation_date", "fuel_product"])
        .reset_index(drop=True)
    )
    logger.info("[br_anp] Returning %d rows (cutoff: %s)", len(out), cutoff)
    return out
