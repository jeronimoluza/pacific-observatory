"""Orange Centrafrique (orangerca.com) -- prepaid plan catalog, snapshot.

orangerca.com is the live Orange Centrafrique storefront (confirmed distinct
from the "orange.cf" domain, which resolves but 301s every path -- including
country-specific ones -- to the Orange Group corporate site orange.com/en;
orange.cf is NOT the CAR operator's site despite the ccTLD).

Each plan-family page (Sakpa/internet, Songo/national calls, international
passes, recharge bonuses) server-renders the plan names and description
bullets, but leaves the price blank in the raw HTML -- Playwright
network-capture on
https://www.orangerca.com/fr/offres-mobile/forfaits-sakpa.html showed the
price is hydrated client-side from a same-origin POST to
/2/calls/getvariantprices.jsp (Tier 1B: "Playwright to discover, plain HTTP
to scrape"). Verified live 2026-09-01: the endpoint requires no cookies or
session state -- a plain `requests.Session` POST with an arbitrary
`menu_uuid` string returns 200 with the full variant-price JSON, confirmed
against a stock `get_session()` (no curl_cffi impersonation needed).

Each plan-family page embeds its own `product_id` in a literal
`postData = 'catalog_id=2&product_id=<N>&lang=fr&menu_uuid=...'` JS string.
Walked all 6 links under /fr/catalogue/offres-mobile.html; 5 resolve to a
product_id, 1 (`les-profils-tarifaires`, product_id=16) is an informational
page with `isShowPrice: "0"` and `price: "0.00"` on its one variant -- not a
purchasable plan, excluded by the `isShowPrice` filter below rather than a
hardcoded product_id skip. `catalogs/forfaits-roaming.html` uses a different,
unwalked mechanism (no `product_id` found) -- not pursued this pass.

    product_id=10  Recharges (bonus credit tiers)
    product_id=13  Forfaits internationaux
    product_id=14  Forfaits d'appels nationaux (Songo)
    product_id=15  Forfaits internet (Sakpa)

IDENTITY: `variantName` is NOT unique within a product -- product_id=10 has
TWO variants both named "Bonus 0" (sku "bonus0" priced 500 FCFA, sku
"bonus0bis" priced 1000 FCFA). This is the same class of defect flagged in
orange_mobile_tariff_bf's fix (see that module's docstring) -- a name-only
`item_name` would silently collide two distinct prices onto one hash. Fixed
by folding the variant's own `sku` into `item_name`
("<family> <variantName> [<sku>]"), which the source itself already uses to
distinguish these two rows.

CURRENCY: the API's `currency_frequency` field literally says "FCFA" (the
common name for both CFA franc zones), not an ISO code. CAR is CEMAC, not
UEMOA -- the correct ISO 4217 code is XAF (matches `countries.yaml`), NOT
XOF (which is what Burkina Faso, Sierra Leone's West African neighbours,
etc. would use). Hardcoded here rather than taken from the field, since the
field is a display label, not a currency code, and would be wrong for every
CEMAC country if copied literally. `price` is a clean decimal string
("100.00", "25000.00") -- no thousands-separator or minor-unit parsing
needed (contrast the space-separated `originalPriceFrom` display field,
deliberately NOT used here).

EFFECTIVE DATE: each variant carries its own `updatedOn` timestamp
("DD/MM/YYYY HH:MM:SS") -- the CMS's own last-price-change date, not a
scrape-time stamp. Using it as `observation_date` (period_kind:
effective_from) is more accurate than stamping every row with today's
date, since the observed timestamps (2023-07-04 .. 2025-07-09) show most
prices have not changed in 2-3 years -- a single "verified live" run date
would misrepresent how long each price has actually been in effect.
Re-running this fetcher will emit 0 new rows until Orange next edits a
price (bumping `updatedOn` past the stored cutoff), which is the correct
idempotent behaviour for a source with no publish-date-stamped catalog.

Test run (cutoff=2020-01-01): 27 rows (6+4+7+10 across the 4 product
families, all `isActive=="1"` and `isShowPrice=="1"`), 27 distinct
item_name, 0 duplicate observation_hash. Price range 50-25,000 XAF
(median 750). Spot-checked against the live pages: "Sakpa 1000" -> 1,000
XAF (matches forfaits-sakpa.html's rendered "1 000" card), "Forfait
Découverte" -> 960 XAF (matches forfaits-internationaux.html).

coicop_classification: source_curated -- the whole catalog (data, voice,
SMS, international, and recharge-bonus plans) is telecommunication
services, COICOP 08.3.0, matching the convention used for the Burkina Faso
and Sierra Leone Orange tariff sources.
"""

from __future__ import annotations

import logging
from datetime import date, datetime

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Central African Republic"
_SOURCE_KEY = "orange_tariffs_caf"
_CURRENCY = "XAF"
_COICOP_CODE = "08.3.0"
_API_URL = "https://www.orangerca.com/2/calls/getvariantprices.jsp"
_IDENT = ["source_key", "observation_date", "item_name"]

# product_id -> (page URL for source_url/notes, human family label)
_PRODUCT_FAMILIES = {
    "10": (
        "https://www.orangerca.com/fr/offres-mobile/les-recharges.html",
        "Recharges",
    ),
    "13": (
        "https://www.orangerca.com/fr/offres-mobile/forfaits-internationaux.html",
        "Forfaits internationaux",
    ),
    "14": (
        "https://www.orangerca.com/fr/offres-mobile/les-forfaits-d-appels-nationaux.html",
        "Forfaits Songo (appels nationaux)",
    ),
    "15": (
        "https://www.orangerca.com/fr/offres-mobile/forfaits-sakpa.html",
        "Forfaits Sakpa (internet)",
    ),
}


def _parse_updated_on(raw) -> date | None:
    raw = str(raw or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%d/%m/%Y %H:%M:%S").date()
    except ValueError:
        return None


def fetch_orange_tariffs_caf(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    ts = get_scrape_ts()
    rows: list[dict] = []

    for product_id, (page_url, family_label) in _PRODUCT_FAMILIES.items():
        try:
            resp = session.post(
                _API_URL,
                data={
                    "catalog_id": "2",
                    "product_id": product_id,
                    "lang": "fr",
                    "menu_uuid": "po-onboarding-fetch",
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[%s] product_id=%s fetch/parse failed: %s",
                _SOURCE_KEY,
                product_id,
                exc,
            )
            continue

        for v in data.get("variants", []):
            if str(v.get("isActive")) != "1" or str(v.get("isShowPrice")) != "1":
                continue
            try:
                price = float(v.get("price"))
            except (TypeError, ValueError):
                continue
            if price <= 0:
                continue
            obs_date = _parse_updated_on(v.get("updatedOn"))
            if obs_date is None or obs_date <= cutoff:
                continue
            variant_name = str(v.get("variantName", "")).strip()
            sku = str(v.get("sku", "")).strip()
            item_name = f"{family_label} {variant_name} [{sku}]".strip()
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "effective_from",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": _COICOP_CODE,
                "item_name": item_name[:200],
                "price_local": price,
                "currency": _CURRENCY,
                "unit": "plan",
                "source_url": page_url,
                "notes": f"Orange RCA {family_label}, product_id={product_id}, sku={sku}",
                "scrape_ts": ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
