"""FSM Department of Transportation, Communications & Infrastructure (TC&I)
-- national Ship Tariff Regulations for the government field-trip vessels
serving inter-state and outer-island routes.

tci.gov.fm hosts the current "Ship Tariff Regulations" as a static PDF
(``/documents/transportation/marine/tariffs/ship-tariff-amended.pdf``),
linked from the Marine Division regulations page. ``pdfplumber`` extracts
clean prose (no embedded tables for the passenger-fare section; the rate
figures are given as per-mile formulas plus six worked route examples).

Only passenger-facing rows are emitted -- Part 4 "Shipment of Cargo" (per
revenue-ton freight rates, per-head live-animal rates, drum/boat rates) is
producer/business-shipping pricing, not a household consumer price, and is
deliberately NOT extracted.

Extracted rows:

- The two base per-mile administered rates (cabin $0.20/mile, deck
  $0.07/mile) -- the regulation's actual rate-setting mechanism.
- The document's own six worked route examples for each of cabin and deck
  fare (Pohnpei/Chuuk/Kosrae/Yap state-center pairs) -- these are arithmetic
  products of the per-mile rate x distance, but are recorded here because
  they are the concrete, quotable trip price a passenger is actually
  charged (comparable in kind to how a fixed-route fare is typically
  recorded elsewhere in this corpus), and the source document itself
  presents them as the reference fares.
- The special/charter voyage hourly rate ($120.00/hour).
- Onboard meal rates (breakfast/lunch/dinner), sold to passengers on
  request.

COICOP: everything here is passenger sea transport -- ``07.3.4``. Onboard
meals are filed under the same code rather than split out to 11.1.1: they
are a minor, optional add-on to the transport service itself (not a
separate catering establishment), and the regulation prices them in the
same Part 3 "Passenger Fares" section as the fares themselves.

Effective date: the regulation's approval page is dated only "2003" with
the day left blank ("Date:__________, 2003" / "effective August ______,
2003"). Modelled as ``period_kind=effective_from`` with
``effective_from = 2003-08-01`` (month+year are the most precise date the
source gives; exact day unknown). This is a genuinely old, still-current
regulation -- it is the only tariff document under TC&I's live
"Regulations" listing (verified 2026-09-28) and there is no newer
amendment on the site -- but the rates it fixes have very likely not moved
with inflation since 2003. Flagged loudly in YAML notes; not silently
presented as freshly priced.

Currency is USD (FSM's actual currency, no FX conversion needed).
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd
import pdfplumber

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Micronesia, Fed. Sts."
_CURRENCY = "USD"
_SOURCE_KEY = "fm_ship_tariff"
_COICOP = "07.3.4"
_URL = "https://tci.gov.fm/documents/transportation/marine/tariffs/ship-tariff-amended.pdf"
_IDENT = ["source_key", "effective_from", "item_name"]
_EFFECTIVE_FROM = date(2003, 8, 1)

_ROUTE_RE = re.compile(r"([A-Za-z]+)\s+to\s+([A-Za-z]+)\s+[\d,]+\s+miles\s*=\s*\$([\d.]+)")
_MEAL_RE = re.compile(r"\$([\d.]+)\s+per\s+(breakfast|lunch|dinner)", re.I)
_SPECIAL_VOYAGE_RE = re.compile(r"rate of \$([\d,.]+) per hour")
# Anchored to the ">=100 miles" clause (3.1.3) -- a separate, lower flat
# per-mile rate applies to <100-mile "Point to point" hops (3.1.2, $0.18/mi)
# and is not the rate used by any of the six illustrated state-center routes.
_CABIN_MILE_RE = re.compile(r"100 miles or more shall be charged a fare of \$([\d.]+) per mile")
_DECK_MILE_RE = re.compile(r"Deck passengers shall be charged \$([\d.]+) per mile")


def _price(text: str) -> float | None:
    try:
        val = float(text.replace(",", ""))
    except ValueError:
        return None
    return val if val > 0 else None


def _split_cabin_deck(full_text: str) -> tuple[str, str]:
    marker = "3.1.4."
    idx = full_text.find(marker)
    if idx == -1:
        return full_text, ""
    return full_text[:idx], full_text[idx:]


def fetch_fm_ship_tariff(cutoff: date) -> pd.DataFrame | None:
    if _EFFECTIVE_FROM <= cutoff:
        logger.info(
            "[%s] no new tariff (effective=%s, cutoff=%s)",
            _SOURCE_KEY,
            _EFFECTIVE_FROM,
            cutoff,
        )
        return None

    session = get_session()
    resp = session.get(_URL, timeout=30)
    resp.raise_for_status()

    with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
        raw_text = "\n".join(p.extract_text() or "" for p in pdf.pages)

    if not raw_text.strip():
        logger.warning("[%s] no text extracted from %s", _SOURCE_KEY, _URL)
        return None

    # Collapse all whitespace (incl. mid-phrase line wraps, e.g. "per\nhour")
    # before regex matching -- pdfplumber line-wraps mid-phrase and a fixed
    # single space in the pattern would otherwise silently miss the wrapped
    # occurrence while still matching an unwrapped one elsewhere in the doc.
    full_text = re.sub(r"\s+", " ", raw_text)

    items: list[tuple[str, float | None, str]] = []

    cabin_text, deck_text = _split_cabin_deck(full_text)

    m = _CABIN_MILE_RE.search(cabin_text)
    if m:
        items.append(("Cabin passenger -- per-mile rate (>=100 miles)", _price(m.group(1)), "USD/mile"))
    for origin, dest, fare in _ROUTE_RE.findall(cabin_text):
        items.append((f"Cabin passenger fare -- {origin} to {dest}", _price(fare), "USD/trip"))

    m = _DECK_MILE_RE.search(deck_text)
    if m:
        items.append(("Deck passenger -- per-mile rate", _price(m.group(1)), "USD/mile"))
    for origin, dest, fare in _ROUTE_RE.findall(deck_text):
        # Source PDF has a one-off typo, "Pohpei", in the deck-fare table only
        # (all 5 other occurrences of the name across the document spell it
        # correctly); normalized so the same route reads identically to its
        # cabin-fare counterpart above.
        origin = "Pohnpei" if origin == "Pohpei" else origin
        items.append((f"Deck passenger fare -- {origin} to {dest}", _price(fare), "USD/trip"))

    m = _SPECIAL_VOYAGE_RE.search(full_text)
    if m:
        items.append(("Special/charter voyage -- hourly rate", _price(m.group(1)), "USD/hour"))

    for amount, meal in _MEAL_RE.findall(full_text):
        items.append((f"Onboard meal -- {meal.lower()}", _price(amount), "USD/meal"))

    items = [it for it in items if it[1] is not None]
    if not items:
        logger.warning("[%s] no tariff rows parsed from %s", _SOURCE_KEY, _URL)
        return None

    ts = get_scrape_ts()
    rows = []
    for item_name, price_local, unit in items:
        row = {
            "observation_date": _EFFECTIVE_FROM.isoformat(),
            "period_kind": "effective_from",
            "country": _COUNTRY,
            "subnational_area": None,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP,
            "item_name": item_name,
            "price_local": price_local,
            "currency": _CURRENCY,
            "unit": unit,
            "source_url": _URL,
            "notes": (
                "Regulation approved/effective 2003 (exact day not given in the "
                "source PDF); still the only tariff document listed under TC&I's "
                "live marine Regulations page as of 2026-09-28, but rates are "
                "very likely unrevised since 2003 -- treat as a stale administered "
                "rate, not a freshly re-priced one."
            ),
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows)
