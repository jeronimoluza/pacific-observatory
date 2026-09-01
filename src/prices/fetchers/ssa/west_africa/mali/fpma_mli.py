"""FAO GIEWS FPMA Tool — Mali domestic market prices (Bucket 1, country-bound).

FAO's Food Price Monitoring and Analysis (FPMA) tool republishes national market-
price panels submitted by in-country monitoring partners through an open, public,
unauthenticated Django REST API (``fpma.fao.org/giews/v4/global/price_module/api/v1/``)
that backs its Angular front end at ``fpma.fao.org/giews/fpmat4/``. For Mali the
underlying reporting partner is Afrique Verte (a Sahel-wide cereals market-
information NGO, not WFP or FEWS NET — genuinely complementary to the existing
``wfp_prices`` manifest, which draws from HDX/WFP VAM). Verified live 2026-09-01:
35 series for ``iso3_country_code=MLI``, covering millet/sorghum/maize/rice
(local + imported) at wholesale, across Bamako, Sikasso, Mopti, Gao, Kayes,
Segou, Koutiala markets; currency XOF throughout (matches countries.yaml);
monthly cadence, most recent ``end_date`` 2026-08-01 (current, not stale).

``FpmaSerie/?iso3_country_code=<ISO3>`` lists each (market, commodity,
price_type) series with a stable ``uuid``. ``FpmaSeriePrice/<uuid>?periodicity=
monthly`` returns that series' full monthly time series as ``datapoints``. There
is no country-scoped page-2 test needed — this is a REST API, not a paginated
catalogue crawl; enumerability is proven by the FpmaSerie list itself returning
distinct series.

Price values are exactly as FAO/Afrique Verte publish them, tied to
``measure_unit_label`` (typically ``100 kg`` for cereals) — NOT converted to a
per-kg figure. Downstream must read the unit, not assume a base unit; the
``conversion_factor`` field FAO also returns is their own real-price-deflation
factor, not a unit normalizer, and is not applied here (mirrors the sibling
WFP/FEWS-NET fetchers, which also report each source's native reporting unit
unmodified).

Each series is (market, commodity, price_type) — NOT commodity alone. The
market name is carried in ``subnational_area`` (also folded into the row
identity hash) so that e.g. Bamako/Sikasso/Mopti Millet observations for the
same month remain distinct rows rather than colliding into one.

All five commodities this source emits (Rice, Rice (imported), Millet, Maize,
Sorghum) are COICOP 01.1.1 (bread and cereals) — a single class, so this is a
narrow source: ``coicop_classification: source_curated`` with
``coicop_codes: ["01.1.1"]`` in the manifest, and every row is stamped with
that code directly rather than deferred to the classifier.
"""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_SERIE_LIST_URL = "https://fpma.fao.org/giews/v4/global/price_module/api/v1/FpmaSerie/"
_SERIE_PRICE_URL = (
    "https://fpma.fao.org/giews/v4/global/price_module/api/v1/FpmaSeriePrice/{uuid}"
)
_ISO3 = "MLI"
_SOURCE_KEY = "fpma_mli"
_COICOP_CODE = "01.1.1"  # all 5 commodities (rice/rice-imported/millet/maize/sorghum)
_IDENT = ["source_key", "observation_date", "item_name", "unit", "subnational_area"]


def _list_series(session) -> list[dict]:
    try:
        resp = session.get(
            _SERIE_LIST_URL,
            params={"iso3_country_code": _ISO3, "format": "json", "page_size": 200},
            timeout=60,
        )
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] series list request failed: %s", _SOURCE_KEY, exc)
        return []
    return payload.get("results", [])


def _series_datapoints(session, serie: dict) -> list[dict]:
    uuid = serie["uuid"]
    try:
        resp = session.get(
            _SERIE_PRICE_URL.format(uuid=uuid),
            params={"periodicity": "monthly", "format": "json"},
            timeout=60,
        )
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] price request failed for %s: %s", _SOURCE_KEY, uuid, exc)
        return []
    return payload.get("datapoints", [])


def fetch_fpma_mli(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    series = _list_series(session)
    if not series:
        logger.warning("[%s] no series returned for %s", _SOURCE_KEY, _ISO3)
        return None

    ts = get_scrape_ts()
    rows: list[dict] = []
    for serie in series:
        item_name = str(serie.get("commodity_name") or "").strip()
        market = str(serie.get("market_name") or "").strip()
        price_type = str(serie.get("price_type") or "").strip() or "WHOLESALE"
        currency = str(serie.get("currency") or "").strip() or None
        unit = str(serie.get("measure_unit_label") or "").strip() or None
        if not item_name:
            continue
        for dp in _series_datapoints(session, serie):
            obs = pd.to_datetime(dp.get("date"), errors="coerce")
            if pd.isna(obs):
                continue
            obs = obs.date()
            if obs <= cutoff:
                continue
            price = pd.to_numeric(dp.get("price_value"), errors="coerce")
            if pd.isna(price) or price <= 0:
                continue
            usd = dp.get("price_value_dollar")
            row = {
                "observation_date": obs.isoformat(),
                "period_kind": "monthly_avg",
                "country": "Mali",
                "source_key": _SOURCE_KEY,
                "coicop_code": _COICOP_CODE,
                "item_name": item_name,
                "subnational_area": market or None,
                "price_local": round(float(price), 4),
                "currency": currency,
                "unit": unit,
                "source_url": "https://fpma.fao.org/giews/fpmat4/",
                "notes": (
                    f"{price_type}; market={market}; FAO GIEWS FPMA "
                    f"(reporting partner: Afrique Verte); usd~"
                    f"{usd if usd is not None else 'na'}"
                ),
                "scrape_ts": ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    logger.info(
        "[%s] %d monthly rows from %d series (cutoff=%s)",
        _SOURCE_KEY,
        len(rows),
        len(series),
        cutoff,
    )
    return pd.DataFrame(rows) if rows else None
