"""Monitorul Preturilor (Romania) -- the Competition Council's official
retail price-comparison platform.

Publishes the observed shelf price of ~23,000 catalogued grocery SKUs at
every participating store of every major Romanian chain (Auchan, Carrefour,
Cora, Kaufland, Lidl, Mega Image, Penny, Profi, Selgros, ...), refreshed
daily. This is a price-LEVEL panel, not an index -- `analytical_role:
official_avg`.

RECOVERED FROM A STALE BLOCKER VERDICT. `known_blockers.md` filed this host
under "DNS resolves but no usable response -- expired or mismatched TLS
certificate, or TCP timeout on every profile including verify=False". The
first half is right and the second is not: the certificate really is
mismatched, but `verify=False` returns a live 200 on every path (re-probed
2026-09-11 with both `curl_cffi` and plain `requests`). Hence
`_SESSION.verify = False` below -- it is load-bearing, not defensive.

The site is a Kendo UI single-page app, so the front page carries no data.
Its jQuery layer reads a wide-open ASP.NET Web API under a base path held
in a global `wsURL` variable declared inline in the page HTML:

    var wsURL = '/pmonsvc/Retail'

Endpoints used (no auth, no cookie, no token):

  /GetProductCategories
      21 top-level grocery categories (parentId "1") plus subcategories.
  /GetCatalogProductsByNameNetwork?CSVcategids=<catid>
      the catalog for one category: {"Items":[{"id","name",...}]}. No
      prices here -- this is the product dictionary.
  /GetStoresForProductsByUat?uatId=<uat>&csvprodids=<id,id,...>
      THE PRICED ENDPOINT. Returns every store in the административная
      unit, each with a `Products[]` array holding the requested catalog
      products as that store stocks them: store-specific product `name`,
      `price`, `unit`, `brand`, `retailcategname` and `pricedate`.

GOTCHA -- the parameterless forms 404. This is ASP.NET Web API action
selection by parameter signature, so `/GetStoresForProductsByUat?uatId=X`
alone returns a JSON 404 ("No action was found on the controller") and only
answers once `csvprodids` is also present. Likewise `/GetProductsFromStore
?categid=&storeid=` answers 200 with a literal empty list for every
(category, store) pair tried -- it is not the route the SPA actually uses
for prices, despite being the one that reads like it. Do not "fix" either
by widening the parameter set blindly; the working shape is the one above.

SCOPE, deliberately bounded to Bucharest. The UAT (administrative unit)
axis is a full cross product: every one of ~23k catalog products is priced
at every store in the queried UAT, and Bucharest alone returns 50 stores.
Querying more UATs multiplies row count by the number of UATs for very
little new information, since Romanian chains price nationally. Bucharest
is the single richest UAT (all chains present, incl. Cash & Carry).
Additional UATs are a one-line change to `_UAT_IDS`, resolvable via
/GetUATByName?uatname=<city>.

SCOPE, deliberately collapsed on the store axis. PRICE_COLUMNS has no
outlet slot (same constraint that made `ua_minfin_fuel` fold oblast into
item_name). Emitting all 50 Bucharest stores would emit up to 50 rows that
differ only in a dimension the schema cannot carry, and they would then
collide on `observation_hash` and be silently deduplicated to one
arbitrary survivor. So this fetcher keeps ONE store per retail chain --
the first seen -- and records the chain in `subnational_area` as
"Bucuresti / <CHAIN>" so the identity tuple stays unique. item_name is
left as the retailer's own product string, unpolluted, because
`coicop_classification: classifier` means the downstream head reads it.
The surviving store's name rides in `notes`.

Idempotence: `observation_date` is the API's own `pricedate` (the date the
price was observed, DD.MM.YYYY HH:MM), not the fetch date. Prices move
slowly, so run 1 emits the whole panel and later runs emit only the SKUs
whose pricedate has advanced past the cutoff.
"""

from __future__ import annotations

import logging
from datetime import date, datetime

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_API = "https://monitorulpreturilor.info/pmonsvc/Retail"
_LANDING = "https://monitorulpreturilor.info/"
_COUNTRY = "Romania"
_CURRENCY = "RON"
_SOURCE_KEY = "ro_monitorul_preturilor"
_IDENT = ["source_key", "observation_date", "item_name", "subnational_area"]

# Municipiul Bucuresti, from /GetUATByName?uatname=Bucuresti
_UAT_IDS = {"179132": "Bucuresti"}

# How many catalog product ids to ask for per priced call. 50 ids returns
# ~50 stores x 50 products in ~1.6s; larger batches make the response
# quadratically bigger for no throughput gain.
_BATCH = 50

# Retailers type the unit field by hand, so it arrives as a long free-text
# tail ("k", "bu", "a", "cv", "1kg", "500g", "525g.600g", ...). Only the
# unambiguous forms are normalised; anything else is passed through
# lowercased rather than guessed, because the unrecognised values usually
# carry a real pack size that tier-a can parse.
_UNIT_MAP = {
    "PC": "each",
    "PIECES": "each",
    "BUC": "each",
    "BUC.": "each",
    "BU": "each",
    "BUCATA": "each",
    "BUCATI": "each",
    "K": "kg",
    "KG": "kg",
    "KILOGRAM": "kg",
    "L": "L",
    "LITRU": "L",
}


def _session():
    s = get_session()
    # The host serves a mismatched certificate; see the module docstring.
    s.verify = False
    s.headers.update({"Accept": "application/json", "Referer": _LANDING})
    return s


def _get(session, path: str):
    try:
        resp = session.get(f"{_API}{path}", timeout=120)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"{_SOURCE_KEY}: request failed {path[:80]} -- {exc}")
        return None
    if resp.status_code != 200:
        logger.warning(f"{_SOURCE_KEY}: HTTP {resp.status_code} on {path[:80]}")
        return None
    try:
        return resp.json()
    except ValueError:
        logger.warning(f"{_SOURCE_KEY}: non-JSON body on {path[:80]}")
        return None


def _parse_pricedate(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return datetime.strptime(raw.split(" ")[0], "%d.%m.%Y").date()
    except ValueError:
        return None


def fetch_ro_monitorul_preturilor(cutoff: date) -> pd.DataFrame | None:
    session = _session()

    # Chain id -> chain name. Half the ids are GLN barcodes
    # (5940475006709 = CARREFOUR, 4055329000008 = LIDL DISCOUNT SRL), so
    # the raw id is unusable as a label.
    networks = {
        n["id"]: n.get("name") or n["id"]
        for n in ((_get(session, "/GetRetailNetworks") or {}).get("Items") or [])
        if n.get("id")
    }
    logger.info(f"{_SOURCE_KEY}: {len(networks)} retail networks")

    cats = (_get(session, "/GetProductCategories") or {}).get("Items") or []
    top = [c for c in cats if c.get("parentId") == "1" and c.get("id")]
    if not top:
        logger.warning(f"{_SOURCE_KEY}: no top-level categories returned")
        return None
    logger.info(f"{_SOURCE_KEY}: {len(top)} top-level categories")

    product_ids: list[str] = []
    seen_ids: set[str] = set()
    for cat in top:
        payload = _get(
            session, f"/GetCatalogProductsByNameNetwork?CSVcategids={cat['id']}"
        )
        items = (payload or {}).get("Items") or []
        for item in items:
            pid = item.get("id")
            if pid and pid not in seen_ids:
                seen_ids.add(pid)
                product_ids.append(pid)
        logger.info(f"{_SOURCE_KEY}: category {cat['name']} -> {len(items)} products")
    logger.info(f"{_SOURCE_KEY}: {len(product_ids)} catalog products")

    scrape_ts = get_scrape_ts()
    rows: list[dict] = []
    for uat_id, uat_name in _UAT_IDS.items():
        # One row per (chain, retailer product string); the store axis is
        # collapsed -- see the module docstring.
        seen_keys: set[tuple[str, str]] = set()
        for start in range(0, len(product_ids), _BATCH):
            batch = ",".join(product_ids[start : start + _BATCH])
            payload = _get(
                session,
                f"/GetStoresForProductsByUat?uatId={uat_id}&csvprodids={batch}",
            )
            for store in (payload or {}).get("Items") or []:
                network_id = (store.get("retailnetwork") or {}).get("id") or ""
                network = networks.get(network_id, network_id)
                store_name = store.get("name") or ""
                for prod in store.get("Products") or []:
                    name = (prod.get("name") or "").strip()
                    price = prod.get("price")
                    if not name or price is None or price <= 0:
                        continue
                    obs_date = _parse_pricedate(prod.get("pricedate"))
                    if obs_date is None or obs_date <= cutoff:
                        continue
                    key = (network, name.upper())
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    unit_raw = (prod.get("unit") or "").strip().upper()
                    row = {
                        "observation_date": obs_date.isoformat(),
                        "period_kind": "snapshot",
                        "country": _COUNTRY,
                        "subnational_area": f"{uat_name} / {network}"
                        if network
                        else uat_name,
                        "source_key": _SOURCE_KEY,
                        "item_name": name,
                        "price_local": float(price),
                        "currency": _CURRENCY,
                        "unit": _UNIT_MAP.get(unit_raw, unit_raw.lower() or None),
                        "source_url": _LANDING,
                        "notes": " | ".join(
                            p
                            for p in (
                                store_name,
                                prod.get("brand"),
                                prod.get("retailcategname"),
                            )
                            if p
                        )
                        or None,
                        "scrape_ts": scrape_ts,
                    }
                    row["observation_hash"] = make_hash(row, _IDENT)
                    rows.append(row)

    if not rows:
        logger.info(f"{_SOURCE_KEY}: no observations newer than {cutoff}")
        return None
    logger.info(f"{_SOURCE_KEY}: {len(rows)} rows")
    return pd.DataFrame(rows)
