"""ODEPA wholesale fruit & vegetable prices (Chile) — full daily catalogue.

Chile's Ministry of Agriculture (ODEPA) publishes a CKAN-hosted, year-partitioned
CSV of daily wholesale min/max/avg prices and traded volume per product/variety/
quality at each regional wholesale market (Lo Valledor, Femacal, etc). This is
the only clean official-average wholesale feed for Chilean fresh produce — the
supermarket sources in this shard are retail-only. One file per year, all
products: this fetcher is general on purpose (grab everything, not just the
missing leaves). COICOP is deferred to the downstream classifier — ``item_name``
is ODEPA's Spanish product/variety/quality label.

The CKAN dataset resource list is resolved at run time via ``package_show`` (the
resource UUID for a given year can change); this fetcher pulls the current and
prior calendar year's CSVs on every run so a year turnover does not need a code
change. Prices use Chilean-locale decimals (comma, e.g. ``4000,0000``). Per-market
rows are collapsed to a national daily average per (product, variety, quality,
unit); the market count and price range are kept in ``notes``.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_CKAN = "https://datos.odepa.gob.cl/api/3/action/package_show"
_DATASET = "precios-mayoristas-de-frutas-y-hortalizas"
_COUNTRY = "Chile"
_CURRENCY = "CLP"
_SOURCE_KEY = "odepa_cl_wholesale"
_IDENT = ["source_key", "observation_date", "item_name", "unit"]

_C_DATE = "Fecha"
_C_PRODUCT = "Producto"
_C_VARIETY = "Variedad / Tipo"
_C_QUALITY = "Calidad"
_C_UNIT = "Unidad de comercializacion"
_C_REGION = "Region"
_C_MARKET = "Mercado"
_C_MIN = "Precio minimo"
_C_MAX = "Precio maximo"
_C_AVG = "Precio promedio"

# Hand-curated COICOP 2018 leaf per ODEPA `Producto`, built by enumerating all
# 317 distinct product+variety item_names (81 distinct Productos) in the
# collected catalogue (2026-09-11). Keyed on Producto: the Variedad is a
# cultivar and collapses to the same leaf, with `_COICOP_BY_VARIETY` holding the
# one case where it does not. Emitted as the row's `coicop_code` for
# classify.py's narrow_source short-circuit; the manifest stays
# `coicop_classification: classifier` so the rows keep reaching the corpus.
#
# Audited against the production classifier: 95.8% row agreement, wrong on 7
# names / 5,667 rows -- all cross-language false friends or fresh-vs-processed
# slips. `Tuna` (Chilean Spanish for prickly pear, sold by the 16 kg crate) was
# filed under Tunas/skipjack FISH; `Zapallo (Camote)`, a squash cultivar, under
# sweet potatoes; `Poroto verde` and `Poroto granado`, fresh off the wholesale
# floor, under canned and dried respectively.
_COICOP_MAP: dict[str, str] = {
    'Acelga': '01.1.7.1.9',
    'Achicoria': '01.1.7.1.4',
    'Ajo': '01.1.7.4.2',
    'Ají': '01.1.7.2.1',
    'Albahaca': '01.1.9.4.0',
    'Alcachofa': '01.1.7.1.6',
    'Apio': '01.1.7.1.9',
    'Arveja Verde': '01.1.7.3.3',
    'Arándano': '01.1.6.4.6',
    'Berenjena': '01.1.7.2.3',
    'Betarraga': '01.1.7.4.9',
    'Breva': '01.1.6.1.4',
    'Bruselas': '01.1.7.1.2',
    'Brócoli': '01.1.7.1.3',
    'Caigua': '01.1.7.2.9',
    'Camote': '01.1.7.5.2',
    'Caqui': '01.1.6.5.5',
    'Cebolla': '01.1.7.4.3',
    'Cebollín': '01.1.7.4.4',
    'Cebollín baby': '01.1.7.4.4',
    'Cereza': '01.1.6.3.4',
    'Chirimoya': '01.1.6.1.9',
    'Choclo': '01.1.7.4.8',
    'Ciboulette': '01.1.7.4.4',
    'Cilantro': '01.1.9.4.0',
    'Ciruela': '01.1.6.3.6',
    'Coco': '01.1.6.1.8',
    'Coliflor': '01.1.7.1.3',
    'Corazón de apio': '01.1.7.1.9',
    'Damasco': '01.1.6.3.3',
    'Durazno': '01.1.6.3.5',
    'Espinaca': '01.1.7.1.5',
    'Espárragos': '01.1.7.1.1',
    'Frambuesa': '01.1.6.4.3',
    'Frutilla': '01.1.6.4.5',
    'Granada': '01.1.6.5.9',
    'Guayaba': '01.1.6.1.5',
    'Haba': '01.1.7.3.9',
    'Higo': '01.1.6.1.4',
    'Jengibre': '01.1.9.4.0',
    'Kiwi': '01.1.6.5.2',
    'Lechuga': '01.1.7.1.4',
    'Limón': '01.1.6.2.2',
    'Locoto': '01.1.7.2.1',
    'Mandarina': '01.1.6.2.4',
    'Mango': '01.1.6.1.5',
    'Manzana': '01.1.6.3.1',
    'Maracuyá': '01.1.6.1.9',
    'Melón': '01.1.6.5.3',
    'Membrillo': '01.1.6.3.2',
    'Mora': '01.1.6.4.4',
    'Naranja': '01.1.6.2.3',
    'Nectarín': '01.1.6.3.5',
    'Níspero': '01.1.6.3.9',
    'Orégano': '01.1.9.4.0',
    'Palta': '01.1.6.1.1',
    'Papa': '01.1.7.5.1',
    'Papaya': '01.1.6.1.6',
    'Pepino dulce': '01.1.6.5.9',
    'Pepino ensalada': '01.1.7.2.2',
    'Pera': '01.1.6.3.2',
    'Pera asiática': '01.1.6.3.2',
    'Perejil': '01.1.9.4.0',
    'Pimiento': '01.1.7.2.1',
    'Piña': '01.1.6.1.7',
    'Plátano': '01.1.6.1.2',
    'Pomelo': '01.1.6.2.1',
    'Poroto granado': '01.1.7.3.1',
    'Poroto verde': '01.1.7.3.2',
    'Puerro': '01.1.7.4.4',
    'Rabanito': '01.1.7.4.9',
    'Ramas de apio': '01.1.7.1.9',
    'Repollo': '01.1.7.1.2',
    'Sandia': '01.1.6.5.4',
    'Tomate': '01.1.7.2.4',
    'Tumbo': '01.1.6.1.9',
    'Tuna': '01.1.6.1.9',
    'Uva': '01.1.6.5.1',
    'Zanahoria': '01.1.7.4.1',
    'Zapallo': '01.1.7.2.5',
    'Zapallo italiano': '01.1.7.2.5',
}

# (Producto, Variedad) pairs where the cultivar changes the leaf.
_COICOP_BY_VARIETY: dict[tuple[str, str], str] = {
    ('Plátano', 'Barraganete'): '01.1.7.5.7',
}


def _coicop_for(product: str, variety: str) -> str | None:
    """Curated leaf for an ODEPA product, or None to defer to the classifier.

    "Fruto del paraiso" is deliberately absent -- the label could not be
    resolved to a species with confidence.
    """
    hit = _COICOP_BY_VARIETY.get((product, variety))
    return hit if hit else _COICOP_MAP.get(product)


def _resolve_csv_urls(session, years: list[int]) -> dict[int, str]:
    try:
        r = session.get(f"{_CKAN}?id={_DATASET}", timeout=60)
        r.raise_for_status()
        resources = r.json()["result"]["resources"]
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] CKAN lookup failed: %s", _SOURCE_KEY, exc)
        return {}
    urls: dict[int, str] = {}
    for res in resources:
        name = res.get("name", "")
        url = res.get("url", "")
        if res.get("format", "").upper() != "CSV":
            continue
        m = re.search(r"(19|20)\d{2}", name) or re.search(r"(19|20)\d{2}", url)
        if not m:
            continue
        year = int(m.group(0))
        if year in years:
            urls[year] = url
    return urls


def _to_number(s: pd.Series) -> pd.Series:
    return pd.to_numeric(
        s.astype(str).str.replace(",", ".", regex=False), errors="coerce"
    )


def _national_rows(df: pd.DataFrame, url: str, cutoff: date) -> list[dict]:
    df = df.copy()
    df["obs"] = pd.to_datetime(df[_C_DATE], errors="coerce").dt.date
    df["avg_price"] = _to_number(df[_C_AVG])
    df["min_price"] = _to_number(df[_C_MIN])
    df["max_price"] = _to_number(df[_C_MAX])
    df = df[df["obs"].notna() & df["avg_price"].notna()]
    df = df[df["avg_price"] > 0]
    df = df[df["obs"] > cutoff]
    if df.empty:
        return []

    ts = get_scrape_ts()
    keys = [_C_PRODUCT, _C_VARIETY, _C_QUALITY, _C_UNIT, "obs"]
    for k in keys:
        if k not in df.columns:
            df[k] = ""
    grp = df.groupby(keys, dropna=False)
    out: list[dict] = []
    for (product, variety, quality, unit, obs), g in grp:
        product = str(product).strip()
        if not product:
            continue
        variety = str(variety).strip()
        quality = str(quality).strip()
        name = product
        if variety and variety.lower() not in ("sin especificar", "nan"):
            name = f"{product} ({variety})"
        price = float(g["avg_price"].mean())
        if not 0 < price < 1e10:
            continue
        pmin = g["min_price"].min()
        pmax = g["max_price"].max()
        markets = g[_C_MARKET].nunique() if _C_MARKET in g.columns else None
        row = {
            "observation_date": obs.isoformat(),
            "period_kind": "daily",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": name,
            "coicop_code": _coicop_for(product, variety),
            "price_local": round(price, 4),
            "currency": _CURRENCY,
            "unit": str(unit).strip() or None,
            "source_url": url,
            "notes": (
                f"wholesale; quality={quality or 'n/a'}; national avg of "
                f"{markets if markets is not None else len(g)} market obs; "
                f"range {pmin:.2f}-{pmax:.2f}"
            ),
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        out.append(row)
    return out


def fetch_odepa_cl_wholesale(cutoff: date) -> pd.DataFrame | None:
    today = date.today()
    years = sorted({today.year, today.year - 1})
    session = get_session()
    urls = _resolve_csv_urls(session, years)
    if not urls:
        return None

    frames: list[pd.DataFrame] = []
    for year, url in urls.items():
        try:
            resp = session.get(url, timeout=180)
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] CSV fetch failed for %d: %s", _SOURCE_KEY, year, exc)
            continue
        resp.encoding = resp.apparent_encoding or "utf-8"
        df = pd.read_csv(io.StringIO(resp.text), low_memory=False)
        rows = _national_rows(df, url, cutoff)
        if rows:
            frames.append(pd.DataFrame(rows))

    if not frames:
        return None
    out = pd.concat(frames, ignore_index=True)
    logger.info(
        "[%s] %d national daily rows (cutoff=%s)", _SOURCE_KEY, len(out), cutoff
    )
    return out
