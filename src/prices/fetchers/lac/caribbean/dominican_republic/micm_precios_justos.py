"""MICM "Precios Justos" (Dominican Republic) — statutory price-monitoring feed
run by the Ministry of Industry, Commerce and MSMEs, published live at
https://preciosjustos.micm.gob.do/. The public page is a React SPA that pulls
its whole catalog from a same-origin JSON API (found by reading the bundled
JS for the `$.get("/api/productos", ...)` call) — no auth, no pagination,
one GET returns the entire monitored catalog (~680 products spanning the
Canasta Basica plus general categories like Pan, Vegetales, Carnes, Lacteos,
Granos, Embutidos, Navidad, Juguetes, Otros — a broad consumer-protection
survey, not food-only). Each product carries a single national
`priceAverages[0]` (verified live: every product in the catalog has exactly
one value in that array, never per-market), plus the list of markets it was
sourced from in `inMarketsSpecial` (kept in notes). The API returns no
per-row date, so this is a same-run snapshot — accumulated across runs like
the other snapshot fetchers in this pipeline (see hk_afcd_wholesale). COICOP
is deferred to the downstream classifier.
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime, timezone

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://preciosjustos.micm.gob.do/api/productos"
_COUNTRY = "Dominican Republic"
_CURRENCY = "DOP"
_SOURCE_KEY = "do_micm_precios_justos"
_IDENT = ["source_key", "observation_date", "item_name", "unit"]

_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _rows(products: list[dict], obs_date: date) -> list[dict]:
    ts = get_scrape_ts()
    out: list[dict] = []
    for p in products:
        name = str(p.get("name") or "").strip()
        averages = p.get("priceAverages") or []
        if not name or not averages:
            continue
        try:
            price = float(averages[0])
        except (TypeError, ValueError):
            continue
        if not 0 < price < 1_000_000:
            continue
        unit = str(p.get("unit") or "").strip() or None
        category = str(p.get("category") or "").strip()
        markets = p.get("inMarketsSpecial") or []
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": name,
            "price_local": round(price, 2),
            "currency": _CURRENCY,
            "unit": unit,
            "source_url": _URL,
            "notes": f"category={category}; national avg across markets: {', '.join(markets)}"[
                :500
            ],
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        out.append(row)
    return out


def fetch_do_micm_precios_justos(cutoff: date) -> pd.DataFrame | None:
    obs_date = datetime.now(timezone.utc).date()
    if obs_date <= cutoff:
        return None
    session = get_session()
    session.headers.update({"User-Agent": _BROWSER_UA, "Accept": "application/json"})
    # The origin (a small Cloudflare-fronted gov server) intermittently 520s under
    # load; get_session()'s retry adapter doesn't cover 520, so retry it here.
    products = None
    last_exc: Exception | None = None
    for attempt in range(4):
        try:
            resp = session.get(_URL, timeout=60)
            if resp.status_code == 520:
                raise RuntimeError("520 from origin")
            resp.raise_for_status()
            products = resp.json()
            break
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < 3:
                time.sleep(5 * (attempt + 1))
    if products is None:
        logger.warning("[%s] fetch failed after retries: %s", _SOURCE_KEY, last_exc)
        return None
    if not isinstance(products, list):
        logger.warning("[%s] unexpected payload shape: %s", _SOURCE_KEY, type(products))
        return None
    rows = _rows(products, obs_date)
    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
