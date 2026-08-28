"""Precios Claros (Argentina) — statutory cross-chain price-transparency feed.

Government-mandated system (SEPA, Secretaria de Comercio): every large retail
chain reports per-SKU prices daily; preciosclaros.gob.ar exposes an
API-Gateway-fronted REST API (CloudFront + API Gateway key baked into the
public site's own JS, not a secret — same trust model as MICM Precios Justos).
Argentina's equivalent of Israel's Food Price Transparency Law.

The full catalog spans ~70,000 products across ~3,600 branches nationwide; a
full national walk is out of scope for one fetcher run, so this pulls a
representative panel of branches (2 nearest branches at each of 10 points
spread across provinces/regions) and walks the 12 top-level category tree
against that panel, recording the min/max price range returned across the
sampled branches as a national-ish average. This is deliberately broad (whole
category tree, not a targeted commodity extractor) but geographically partial
— widening the branch panel is future work, noted here for the next agent.

No per-row date is exposed by the API (it is a live current-price snapshot,
same as MICM Precios Justos / hk_afcd_wholesale) — emitted as
period_kind="snapshot" dated to the scrape day, accumulated across runs.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_API = "https://d3e6htiiul5ek9.cloudfront.net/prod"
# API-Gateway key embedded in the public site's bundled JS (www.preciosclaros.gob.ar,
# var API_KEY=...) — required by the gateway but not a secret credential.
_API_KEY = "zIgFou7Gta7g87VFGL9dZ4BEEs19gNYS1SOQZt96"
_COUNTRY = "Argentina"
_CURRENCY = "ARS"
_SOURCE_KEY = "ar_precios_claros"

# One point per major region/province capital-ish city, used to pull a
# geographically-spread panel of branch ids via /sucursales?lat=&lng=.
_PANEL_POINTS = [
    ("CABA", -34.6037, -58.3816),
    ("Cordoba", -31.4201, -64.1888),
    ("Rosario_SantaFe", -32.9468, -60.6393),
    ("Mendoza", -32.8895, -68.8458),
    ("Salta", -24.7859, -65.4117),
    ("Neuquen", -38.9516, -68.0591),
    ("MarDelPlata_BsAs", -38.0055, -57.5426),
    ("Tucuman", -26.8083, -65.2176),
    ("Posadas_Misiones", -27.3671, -55.8961),
    ("Ushuaia_TierraDelFuego", -54.8019, -68.3030),
]
_BRANCHES_PER_POINT = 2
_MAX_PANEL_SIZE = 50  # API-documented maxCantSucursalesPermitido
_PAGE_LIMIT = 100  # API-documented maxLimitPermitido
_MAX_PAGES_PER_CATEGORY = (
    60  # safety cap (~6,000 rows/category) against pathological totals
)

_IDENT = ["source_key", "observation_date", "id_categoria", "producto_id"]


def _headers() -> dict:
    return {
        "x-api-key": _API_KEY,
        "User-Agent": "pacific-observatory/prices (+research)",
    }


def _build_panel(session) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for name, lat, lng in _PANEL_POINTS:
        try:
            r = session.get(
                f"{_API}/sucursales",
                params={"lat": lat, "lng": lng, "limit": _BRANCHES_PER_POINT},
                headers=_headers(),
                timeout=30,
            )
            r.raise_for_status()
            payload = r.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[%s] sucursales lookup failed for %s: %s", _SOURCE_KEY, name, exc
            )
            continue
        for suc in payload.get("sucursales", []):
            sid = suc.get("id")
            if sid and sid not in seen:
                seen.add(sid)
                ids.append(sid)
        if len(ids) >= _MAX_PANEL_SIZE:
            break
    return ids[:_MAX_PANEL_SIZE]


def _top_categories(session) -> list[dict]:
    try:
        r = session.get(f"{_API}/categorias", headers=_headers(), timeout=60)
        r.raise_for_status()
        payload = r.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] categorias lookup failed: %s", _SOURCE_KEY, exc)
        return []
    return [c for c in payload.get("categorias", []) if c.get("nivel") == 1]


def _parse_unit(presentacion: str | None) -> str | None:
    if not presentacion:
        return None
    parts = presentacion.strip().split()
    if len(parts) >= 2:
        return parts[1].lower()
    return presentacion.strip() or None


def _walk_category(session, panel_csv: str, cat: dict, today_iso: str) -> list[dict]:
    cat_id = cat["id"]
    cat_name = cat.get("nombre") or cat_id
    ts = get_scrape_ts()
    rows: list[dict] = []
    offset = 0
    for _ in range(_MAX_PAGES_PER_CATEGORY):
        try:
            r = session.get(
                f"{_API}/productos",
                params={
                    "id_categoria": cat_id,
                    "array_sucursales": panel_csv,
                    "offset": offset,
                    "limit": _PAGE_LIMIT,
                },
                headers=_headers(),
                timeout=30,
            )
            r.raise_for_status()
            payload = r.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[%s] productos fetch failed cat=%s offset=%d: %s",
                _SOURCE_KEY,
                cat_id,
                offset,
                exc,
            )
            break
        productos = payload.get("productos", [])
        if not productos:
            break
        for p in productos:
            pmin = p.get("precioMin")
            pmax = p.get("precioMax")
            if pmin is None or pmax is None:
                continue
            price = round((float(pmin) + float(pmax)) / 2, 2)
            if not 0 < price < 1e9:
                continue
            row = {
                "observation_date": today_iso,
                "period_kind": "snapshot",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "id_categoria": cat_id,
                "producto_id": p.get("id"),
                "item_name": p.get("nombre"),
                "price_local": price,
                "currency": _CURRENCY,
                "unit": _parse_unit(p.get("presentacion")),
                "source_url": f"{_API}/productos?id_categoria={cat_id}",
                "notes": (
                    f"categoria={cat_name}; marca={p.get('marca')}; "
                    f"precioMin={pmin}; precioMax={pmax}; "
                    f"branches_sampled={p.get('cantSucursalesDisponible')}"
                ),
                "scrape_ts": ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)
        total = payload.get("total", 0)
        offset += _PAGE_LIMIT
        if offset >= total:
            break
    return rows


def fetch_ar_precios_claros(cutoff: date) -> pd.DataFrame | None:
    today = datetime.now(timezone.utc).date()
    today_iso = today.isoformat()
    if today <= cutoff:
        return None

    session = get_session()
    panel = _build_panel(session)
    if not panel:
        logger.warning(
            "[%s] could not build a branch panel — aborting run", _SOURCE_KEY
        )
        return None
    panel_csv = ",".join(panel)

    categories = _top_categories(session)
    if not categories:
        logger.warning("[%s] could not fetch category tree — aborting run", _SOURCE_KEY)
        return None

    all_rows: list[dict] = []
    for cat in categories:
        all_rows.extend(_walk_category(session, panel_csv, cat, today_iso))

    if not all_rows:
        return None
    logger.info(
        "[%s] %d rows across %d categories, %d-branch panel (cutoff=%s)",
        _SOURCE_KEY,
        len(all_rows),
        len(categories),
        len(panel),
        cutoff,
    )
    return pd.DataFrame(all_rows)
