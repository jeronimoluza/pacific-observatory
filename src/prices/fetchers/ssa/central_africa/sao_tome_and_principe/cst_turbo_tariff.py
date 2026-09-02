"""CST (Companhia Santomense de Telecomunicações) — prepaid "Turbo" bundle tariffs.

CST's /PT/turbo/tarifarios page is static server-rendered HTML with clean tables for
each of its four prepaid voice+data bundle tiers (Turbinho, Turbo+Net, Superturbo+Net,
Turbo Max+Net), each broken into Diário/Semanal/Mensal (daily/weekly/monthly)
durations -- 12 plans total. Verified live 2026-09-01: `pandas.read_html` returns 8
tables, but they come in duplicate PAIRS -- table[2n] is a compact 3-column
("O que inclui" / "Quanto Custa") rendering and table[2n+1] is the SAME plan tier
re-rendered as a wider 4-5 column responsive layout (a desktop-vs-mobile-card
duplicate, same root cause class as the WPML multi-language duplicate trap, just
triggered by CSS breakpoints instead of language switching). Only the even-indexed
tables are used; the odd ones are skipped entirely, not merged.

Row labels carry a footnote reference digit with no separating space
("REFORÇO1", "MENSAL2") -- stripped with a trailing-digit regex.

Currency: page prints "Dbs" (dobras); magnitude (10-330 Dbs per bundle) is
consistent with STN, not pre-2018 STD.

No effective/publication date is printed on this specific page -- period_kind is
snapshot (observation_date = scrape date).

analytical_role: tariff -> PriceObservation.
coicop_classification: source_curated (coicop_codes: ["08.1.0"], matching the
convention used for other prepaid mobile voice+data bundles in this repo, e.g.
vodafone_ki_mobile.yaml, pncc_prepaid_pw.yaml, astca_prepaid_as.yaml).
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://cst.st/PT/turbo/tarifarios"
_COUNTRY = "Sao Tome and Principe"
_CURRENCY = "STN"
_SOURCE_KEY = "stp_cst_turbo_tariff"
_COICOP = "08.1.0"
_IDENT = ["source_key", "observation_date", "item_name"]

_PRICE_RE = re.compile(r"([\d.,]+)\s*Dbs", re.IGNORECASE)
_VALIDITY_RE = re.compile(
    r"v[aá]lid[oa]\s*(?:por)?\s*:?\s*([\w.]+\s*\w*)", re.IGNORECASE
)


def fetch_stp_cst_turbo_tariff(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_URL, timeout=30)
    resp.raise_for_status()

    try:
        tables = pd.read_html(io.StringIO(resp.text))
    except ValueError as exc:
        logger.warning("[%s] no tables found at %s: %s", _SOURCE_KEY, _URL, exc)
        return None

    canonical = [tables[i] for i in range(0, len(tables), 2)]

    items: list[tuple[str, float, str | None]] = []
    for t in canonical:
        if t.shape[1] < 3:
            continue
        for _, r in t.iterrows():
            plan_raw = str(r.iloc[0]).strip()
            cost_cell = str(r.iloc[2]).strip()
            m = _PRICE_RE.search(cost_cell)
            if not m:
                continue
            try:
                price = float(m.group(1).replace(",", "."))
            except ValueError:
                continue
            if price <= 0:
                continue
            plan_name = re.sub(r"\d+$", "", plan_raw).strip()
            vm = _VALIDITY_RE.search(cost_cell)
            validity = vm.group(1).strip() if vm else None
            item_name = f"CST {plan_name}" + (f" ({validity})" if validity else "")
            items.append((item_name, price, validity))

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
    for item_name, price, validity in items:
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": item_name,
            "price_local": price,
            "currency": _CURRENCY,
            "unit": "bundle",
            "coicop_code": _COICOP,
            "source_url": _URL,
            "notes": f"validity={validity or 'unknown'}; CST published tariff in dobras (STN); no effective date printed on page.",
            "scrape_ts": ts_scrape,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows)
