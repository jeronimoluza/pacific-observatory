"""Telecel Guine-Bissau -- retail mobile tariffs and data/voice bundles.

Telecel is a Guinea-Bissau mobile operator (the former Guinetel/Orange
footprint rebranded). `telecel.gw` and `telecelgb.com` are the SAME site --
byte-identical HTML and the same analytics site id -- so only one manifest
exists; `telecelgb.com` is recorded here as an alias, not onboarded twice.

Probed 2026-09-12. The pages are a client-rendered tRPC/Next.js app: the raw
HTML is 369 KB and contains NOT ONE price, so `pandas.read_html` and a plain
regex over the markup both return nothing. A Playwright trace showed the app
hydrating from its own batched tRPC endpoint:

    GET https://telecel.gw/api/trpc/plans.list,bundles.list?batch=1&input=<json>

which answers over plain HTTP with no auth, cookie, or session warm-up -- so
Playwright ran at discovery time only and never runs here.

Two row families, both COICOP 08.3.2.0 (mobile communication services):

* `plans.list` -- the Telecel+ prepaid plan, whose `price` is 0 (the plan
  itself is free to hold). Its VALUE is the per-unit rate card carried in
  sibling fields: callsTelecel / callsOther / callsInternational (XOF per
  minute) and smsTelecel / smsOther (XOF per SMS). Each rate is emitted as its
  own row with an explicit `unit`, because a 0-priced plan row would otherwise
  drop the only per-unit telecom prices the operator publishes.
* `bundles.list` -- prepaid data and combo bundles with a XOF `price`, a
  `volume` string and `validityDays`. `unit` is the bundle's validity so a
  30-day 10,000 XOF bundle is not compared against a 1-day 500 XOF one.

Currency is taken from the plan payload's explicit `currency: "XOF"` field
rather than from countries.yaml, per the skill's "what the site returns wins"
rule; the bundles endpoint carries no currency field and inherits XOF.

Inactive rows (`active: false`) and zero/None prices are dropped. Observed
2026-09-12: 1 plan -> 5 rate rows, 7 active bundles -> 7 rows, 12 total.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
from datetime import date, datetime, timezone

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_BASE = "https://telecel.gw"
_PAGE_URL = f"{_BASE}/planos-tarifarios"
_COUNTRY = "Guinea-Bissau"
_CURRENCY = "XOF"
_SOURCE_KEY = "gw_telecel_tariffs"
_COICOP = "08.3.2.0"
_IDENT = ["source_key", "observation_date", "item_name"]

# Rate fields on a plan record -> (human label suffix, billing unit).
_RATE_FIELDS = {
    "callsTelecel": ("chamadas Telecel", "minute"),
    "callsOther": ("chamadas outras redes", "minute"),
    "callsInternational": ("chamadas internacionais", "minute"),
    "smsTelecel": ("SMS Telecel", "sms"),
    "smsOther": ("SMS outras redes", "sms"),
}


def _prefixed(name: str) -> str:
    """Brand-prefix an item name without doubling it (several bundle names
    already start with "Telecel", e.g. "Telecel Boss 50 Gigas")."""
    name = (name or "").strip()
    return name if name.lower().startswith("telecel") else f"Telecel {name}"


def _validity_unit(days) -> str:
    if not days:
        return "bundle"
    return "1 day" if int(days) == 1 else f"{int(days)} days"


def _trpc(session, procedures: list[str]) -> list:
    """Call the batched tRPC endpoint and return one payload per procedure."""
    payload = {
        str(i): {"json": None, "meta": {"values": ["undefined"]}}
        for i in range(len(procedures))
    }
    url = (
        f"{_BASE}/api/trpc/{','.join(procedures)}"
        f"?batch=1&input={urllib.parse.quote(json.dumps(payload))}"
    )
    resp = session.get(url, timeout=30, headers={"referer": f"{_BASE}/"})
    resp.raise_for_status()
    return [block["result"]["data"]["json"] for block in resp.json()]


def fetch_gw_telecel_tariffs(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    try:
        plans, bundles = _trpc(session, ["plans.list", "bundles.list"])
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        logger.warning("telecel_gw: unusable tRPC payload (%s)", exc)
        return None

    obs_date = datetime.now(timezone.utc).date()
    if obs_date <= cutoff:
        logger.info(
            "telecel_gw: obs_date %s <= cutoff %s — no new rows", obs_date, cutoff
        )
        return None

    scrape_ts = get_scrape_ts()
    rows: list[dict] = []

    def emit(item_name: str, price: float, unit: str) -> None:
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP,
            "item_name": item_name,
            "price_local": float(price),
            "currency": _CURRENCY,
            "unit": unit,
            "source_url": _PAGE_URL,
            "scrape_ts": scrape_ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    for plan in plans or []:
        if not plan.get("active", True):
            continue
        plan_name = plan.get("namePt") or plan.get("nameEn") or "plano"
        currency = plan.get("currency")
        if currency and currency != _CURRENCY:
            logger.warning(
                "telecel_gw: plan %s reports currency %s, expected %s — skipping",
                plan_name,
                currency,
                _CURRENCY,
            )
            continue
        for field, (label, unit) in _RATE_FIELDS.items():
            rate = plan.get(field)
            if not rate or float(rate) <= 0:
                continue
            emit(f"{_prefixed(plan_name)} — {label}", rate, unit)

    for bundle in bundles or []:
        if not bundle.get("active", True):
            continue
        price = bundle.get("price")
        if not price or float(price) <= 0:
            continue
        name = bundle.get("namePt") or bundle.get("nameEn")
        if not name:
            continue
        volume = (bundle.get("volume") or "").strip()
        days = bundle.get("validityDays")
        unit = _validity_unit(days)
        item = _prefixed(name) + (f" ({volume})" if volume else "")
        emit(item, price, unit)

    if not rows:
        logger.warning("telecel_gw: no tariff rows extracted from %s", _PAGE_URL)
        return None
    return pd.DataFrame(rows)
