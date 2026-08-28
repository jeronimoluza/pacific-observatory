"""prix.nc — official New Caledonia price observatory REST API.

prix.nc is the territorial Observatoire des Prix, publishing a documented
Spring-Data-REST / OpenAPI catalog at https://prix.nc/api/v1/v3/api-docs.
This fetcher walks the whole "relevesprix" (price-comparison) resource —
individual price readings tied to (product, store, commune, date) — rather
than a targeted subset. As of onboarding (2026-08) that resource holds
~162k readings across ~22.5k products and 191 stores territory-wide.

The resource is sorted newest-first (`sort=dateReleve,desc`) and paginated
at _PAGE_SIZE; once a page's readings drop to or below `cutoff`, the walk
stops — this makes incremental (daily/weekly) runs cheap while still
supporting a full historical backfill on first run (fallback_date is set
far enough back to capture the site's actual history).

`prix` (integer, no decimals — XPF has no minor subdivision) is the price
as paid for the item as packaged; `item_name` carries the pack size in the
product name text (e.g. "barquette 500 g"), same convention as retailer_sku
spiders — downstream tier-a/classifier parses quantity from the name rather
than trusting a pre-normalized unit price.

Emits PriceObservation rows (analytical_role: official_avg). COICOP tagging
is left to the downstream classifier (coicop_classification: classifier) —
the catalog spans nearly every COICOP division, so it is wide, not narrow.
"""

import logging
from datetime import date, datetime, timezone

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_BASE_URL = "https://prix.nc/api/v1"
_RELEVES_URL = f"{_BASE_URL}/relevesprix"
_COUNTRY = "New Caledonia"
_CURRENCY = "XPF"
_SOURCE_KEY = "nc_prixnc"
_PAGE_SIZE = 500

_IDENT = ["source_key", "source_row_id"]


def fetch_nc_prixnc(cutoff: date) -> pd.DataFrame | None:
    session = get_session()

    rows = []
    # Sorting by dateReleve alone is not a stable order -- many readings share a
    # timestamp, so Spring Data reshuffles ties between page fetches and the same
    # id comes back on more than one page (36% of a full backfill, measured).
    # Dedupe on the API's own row id; the writer only dedupes against the file
    # already on disk, not within an incoming batch.
    seen_ids = set()
    page = 0
    while True:
        resp = session.get(
            _RELEVES_URL,
            params={"size": _PAGE_SIZE, "page": page, "sort": "dateReleve,desc"},
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        embedded = payload.get("_embedded", {})
        key = next(iter(embedded), None)
        items = embedded.get(key, []) if key else []
        if not items:
            break

        crossed_cutoff = False
        for entry in items:
            ms = entry.get("dateReleve")
            if ms is None:
                continue
            obs_date = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date()
            if obs_date <= cutoff:
                crossed_cutoff = True
                continue

            item_name = entry.get("nom")
            price = entry.get("prix")
            row_id = entry.get("id")
            if not item_name or price is None or not row_id:
                continue
            if row_id in seen_ids:
                continue
            seen_ids.add(row_id)

            magasin = entry.get("magasin")
            origine = entry.get("origine")
            promo = " promo" if entry.get("promotion") else ""
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "snapshot",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "source_row_id": row_id,
                "item_name": item_name,
                "price_local": float(price),
                "currency": _CURRENCY,
                "unit": "each",
                "source_url": f"{_RELEVES_URL}/{row_id}",
                "notes": f"store={magasin}; origin={origine}{promo}",
                "scrape_ts": get_scrape_ts(),
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

        page += 1
        total_pages = payload.get("page", {}).get("totalPages", 0)
        if crossed_cutoff or page >= total_pages:
            break

    return pd.DataFrame(rows) if rows else None
