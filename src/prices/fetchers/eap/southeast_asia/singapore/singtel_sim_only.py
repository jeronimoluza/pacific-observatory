"""Singapore -- Singtel SIM Only mobile plan tariff, snapshot.

Singtel's SIM Only plans page
(singtel.com/personal/products-services/mobile/sim-only-plans) is plain
server-rendered React/styled-components HTML -- no anti-bot, no JS
rendering needed, `curl_cffi` gets the full page on the first try.
Verified live 2026-09-06: 200, 362KB, 5 named plan cards each embedding a
promotional monthly rate and the regular (post-promotion) monthly rate
directly in the markup as plain "$X.XX/mth" text next to an
`<h3 class="sc-eqUAAy jRNbUb">` plan-name heading.

Plans found: Enhanced Lite ($24.50/$35.00), Enhanced Core ($36.00/
$40.00), Priority Plus ($49.50/$55.00), Priority Ultra ($72.00/$80.00),
Seniors SIM Only Plan ($6.00, single price -- no promo/regular split
shown for this plan). This fetcher emits BOTH the promotional and regular
price as separate rows (`item_name` suffixed "(promo)"/"(regular)") since
both are genuinely displayed, real, current prices -- not a derived
duplicate -- except for the Seniors plan, which only has one price to
emit.

The site's own class names (`sc-eqUAAy`, `sc-5ff7e569-...`) are
styled-components hashes that WILL change on a future deploy -- this is
brittle by nature of the platform, but no more stable selector exists in
the rendered markup; if this fetcher starts returning 0 rows, the hash
suffix is the first thing to re-check against a fresh page fetch.

No archive of prior plan pricing exists -- snapshots the CURRENT catalog
each run (period_kind: effective_from = date of the scrape, since the
page carries no explicit "effective from" date of its own).

Currency: SGD, matches countries.yaml. coicop_classification:
source_curated -- COICOP 08.3.0 (telecommunication services).
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_PAGE_URL = "https://www.singtel.com/personal/products-services/mobile/sim-only-plans"
_COUNTRY = "Singapore"
_CURRENCY = "SGD"
_SOURCE_KEY = "sg_singtel_sim_only"
_COICOP_CODE = "08.3.0"
_IDENT = ["source_key", "observation_date", "item_name"]

_PLAN_NAME_RE = re.compile(
    r'<h3 class="sc-eqUAAy jRNbUb"><span[^>]*>([^<]+)</span></h3>'
)
_PRICE_RE = re.compile(r"\$([\d,]+\.\d{2})/mth")
_WINDOW = 2000


def fetch_sg_singtel_sim_only(cutoff: date) -> pd.DataFrame | None:
    effective_from = date.today()
    if effective_from <= cutoff:
        logger.info("[%s] no new release past cutoff=%s", _SOURCE_KEY, cutoff)
        return None

    session = get_session()
    try:
        resp = session.get(_PAGE_URL, timeout=60)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] page fetch failed: %s", _SOURCE_KEY, exc)
        return None

    text = resp.text
    matches = list(_PLAN_NAME_RE.finditer(text))
    if not matches:
        logger.warning("[%s] no plan cards found on %s", _SOURCE_KEY, _PAGE_URL)
        return None

    parsed: list[dict] = []
    for i, m in enumerate(matches):
        plan_name = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else start + _WINDOW
        window = text[start:min(end, start + _WINDOW)]
        prices = _PRICE_RE.findall(window)
        if not prices:
            continue
        if len(prices) >= 2:
            parsed.append({"item_name": f"{plan_name} (promo)", "price_local": float(prices[0].replace(",", ""))})
            parsed.append({"item_name": f"{plan_name} (regular)", "price_local": float(prices[1].replace(",", ""))})
        else:
            parsed.append({"item_name": plan_name, "price_local": float(prices[0].replace(",", ""))})

    if not parsed:
        logger.warning("[%s] no prices parsed from %s", _SOURCE_KEY, _PAGE_URL)
        return None

    ts = get_scrape_ts()
    rows: list[dict] = []
    for p in parsed:
        row = {
            "observation_date": effective_from.isoformat(),
            "period_kind": "effective_from",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP_CODE,
            "item_name": p["item_name"],
            "price_local": p["price_local"],
            "currency": _CURRENCY,
            "unit": "month",
            "source_url": _PAGE_URL,
            "notes": "Singtel SIM Only plan, no-contract mobile",
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
