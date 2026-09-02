# St. Lucia

_Inventory written: 2026-09-01_

Final F&B sweep, lac-agent-A. Cold start — no `lac/` inventory existed for St. Lucia
before this file. Before this pass: 0 sources total, 0 food. CaribeEats (the
delivery aggregator that yielded Grenada/St Kitts/Nevis/Dominica) returns 0
grocery-tagged businesses for its `stlucia` region — the win here came from the
Massy Group's own storefront network instead (same operator family as the
already-onboarded `massy_stores_bb` Barbados and `massy_stores_tt` Trinidad).

| Source name | URL | Channel | Status | Notes |
|---|---|---|---|---|
| Massy Stores St Lucia | https://www.shopmassystoresslu.com/ | supermarket | **SHIPPED** as `massy_stores_slu` | WooCommerce Store API via the `?rest_route=` form (default path 500s, same as the Barbados tenant). Full unbounded run 2026-09-01 (post price-guard fix): 7844 rows, 7844 distinct `product_id`, 7844 distinct `url`, 0 blank names, 0 zero/negative prices, 100% XCD, price range 0.25-373.00 (median 13.41), ~74.1% food-led. 2/2 cold re-fetch spot checks matched. Needed two subclass-level fixes beyond the usual `IMPERSONATE_PROFILE` flag — see "Bugs found" below. |
| CaribeEats (`stlucia` region) | https://backend.caribeeats.com/api/init | — | **NOT APPLICABLE** | 0 businesses returned for `service_id=groceries&region_id=stlucia` — platform has no active grocery vendor for this territory (contrast with Grenada/St Kitts/Nevis/Dominica, which all had at least one). |

## Bugs found and fixed (both scoped to this one spider)

1. `scrapy_impersonate.middleware.RandomBrowserMiddleware.process_request`
   unconditionally overwrites `request.meta["impersonate"]` with a random pick
   from `settings.py`'s `IMPERSONATE_BROWSERS` pool (currently pinned to
   `["chrome120"]`) — it does not check for a pre-existing value, so
   `WooBaseSpider`'s documented `IMPERSONATE_PROFILE` opt-in hook is silently
   clobbered back to chrome120 on every request unless the middleware is also
   disabled for that spider. This tenant 403s on chrome120 (and
   chrome124/131/99) and only clears on safari17_0, so the first attempt at
   scaffolding this spider 403'd immediately despite setting
   `IMPERSONATE_PROFILE = "safari17_0"`. Fixed by following the same
   already-established pattern used in `cassandraonlinemarket_ht.py`: disable
   `RandomBrowserMiddleware` via `custom_settings` scoped to this one spider
   class (merging in `WooBaseSpider.custom_settings` so the base polite-crawl
   settings are preserved) and match the `USER_AGENT` header to the safari17_0
   TLS fingerprint.
2. `WooBaseSpider._item()` only checks `prices.get("price") is None` — it does
   not guard against a zero price. This tenant genuinely emits `price="0"` on
   a handful of stale/out-of-stock listings (7 of the first 7851-row run: e.g.
   "Local Produce Sweet Pepper (per KG)", "Snickers King Size (Each)", both at
   XCD 0.00). Fixed via an `_item()` override in `massy_stores_slu.py` that
   calls `super()._item()` then drops the row if `float(item["price"]) <= 0`.

**No shared file (`settings.py`, `_woo_base.py`) was touched for either fix** —
both are entirely contained in `massy_stores_slu.py`. Fix #1 is not a new
discovery — the pattern already exists as a precedent in the tree — but worth
flagging since the base class's own `IMPERSONATE_PROFILE` docstring reads as if
setting the flag alone were sufficient, which it is not. Fix #2 may be worth
porting to `_woo_base.py` itself (the same zero-price gap likely exists for every
other `WooBaseSpider` subclass) but that is a shared-file change outside this
sweep's mandate — flagged here for a maintainer to decide, not applied.

## COICOP / channel gap after this pass

St. Lucia ends at **1 source / 1 food** (`massy_stores_slu`, supermarket). No
division-02-dedicated, pharmacy, or non-retail coverage yet. Untried this pass:
CK Greaves (a known St Lucia retail group) and a deeper per-country search beyond
the one WebSearch call that surfaced Massy's St Lucia storefront.
