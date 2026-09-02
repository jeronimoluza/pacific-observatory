"""CST (Companhia Santomense de Telecomunicações) — per-minute/SMS voice tariff.

Sibling to cst_turbo_tariff.py (same operator, different rate-card family): this
fetcher covers CST's two flagship per-usage plans -- "Príncipe" (postpaid) and
"Leve Leve" (prepaid) -- rather than the prepaid "Turbo" data+voice bundles.

Verified live 2026-09-01: each plan's page (.../tarifario-principe,
.../tarifario-leve-leve) renders the SAME rate card as multiple `pandas.read_html`
tables that partially overlap -- e.g. Príncipe returns 3 tables where the first two
are voice-only and SMS-only splits, and the third is the full consolidated
(call-type x destination) table. Same duplicate-rendering root cause as the Turbo
page (desktop-vs-compact layout), so only the LAST table on each page is used --
it is always the fully consolidated one, confirmed by row-count (Príncipe:
4 = 2 voice + 2 SMS rows; Leve Leve: 5 = 2 voice + 2 SMS + 1 video row).

Currency: "Dbs" (dobras), comma decimal separator (e.g. "2,76 Dbs p/ Min."),
magnitude consistent with STN.

No effective/publication date is printed -- period_kind: snapshot.

analytical_role: tariff -> PriceObservation.
coicop_classification: source_curated (coicop_codes: ["08.3.0"], per-usage voice/SMS
call charges -- distinct from cst_turbo_tariff's ["08.1.0"] bundled plans).
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_PLANS = [
    (
        "Príncipe (pós-pago)",
        "https://cst.st/PT/pessoal/movel/tarifario-de-voz-pos-pago/tarifario-principe",
    ),
    (
        "Leve Leve (pré-pago)",
        "https://cst.st/PT/pessoal/movel/tarifario-de-voz-pre-pago/tarifario-leve-leve",
    ),
]
_COUNTRY = "Sao Tome and Principe"
_CURRENCY = "STN"
_SOURCE_KEY = "stp_cst_voice_tariff"
_COICOP = "08.3.0"
_IDENT = ["source_key", "observation_date", "item_name"]
_PRICE_RE = re.compile(r"([\d.,]+)\s*Dbs", re.IGNORECASE)


def fetch_stp_cst_voice_tariff(cutoff: date) -> pd.DataFrame | None:
    session = get_session()

    items: list[tuple[str, float]] = []
    for plan_name, url in _PLANS:
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] fetch failed for %s: %s", _SOURCE_KEY, url, exc)
            continue
        try:
            tables = pd.read_html(io.StringIO(resp.text))
        except ValueError as exc:
            logger.warning("[%s] no tables at %s: %s", _SOURCE_KEY, url, exc)
            continue
        if not tables:
            continue
        canonical = tables[-1]  # consolidated table is always the last on the page
        if "Destino" not in canonical.columns or "Preço" not in canonical.columns:
            logger.warning("[%s] unexpected table shape at %s", _SOURCE_KEY, url)
            continue
        for _, r in canonical.iterrows():
            call_type = str(r.iloc[0]).strip()
            destino = str(r["Destino"]).strip()
            price_cell = str(r["Preço"]).strip()
            m = _PRICE_RE.search(price_cell)
            if not m:
                continue
            try:
                price = float(m.group(1).replace(",", "."))
            except ValueError:
                continue
            if price <= 0:
                continue
            item_name = f"CST {plan_name} - {call_type} para {destino}"
            items.append((item_name, price))

    if not items:
        logger.warning("[%s] no tariff rows parsed", _SOURCE_KEY)
        return None

    obs_date = date.today()
    if obs_date <= cutoff:
        logger.info(
            "[%s] scrape date %s <= cutoff %s, skipping", _SOURCE_KEY, obs_date, cutoff
        )
        return None

    ts_scrape = get_scrape_ts()
    rows = []
    for item_name, price in items:
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": item_name,
            "price_local": price,
            "currency": _CURRENCY,
            "unit": "per-use",
            "coicop_code": _COICOP,
            "source_url": "https://cst.st/PT/clientes/tarifarios",
            "notes": "CST published tariff in dobras (STN); no effective date printed on page.",
            "scrape_ts": ts_scrape,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows)
