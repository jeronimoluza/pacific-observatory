# Sweden

_Inventory written: 2026-09-11_

Scope note: single-candidate pass from the onboard4 backlog shard (Sweden was
ranked 172 of 257 COICOP leaves empty). Only `coop.se` was handed to this run;
this file records that outcome plus the already-onboarded set, so the next run
can start from the gap rather than from zero.

Already onboarded before this pass: `willys_se`, `hemkop_se` (both Axfood-group
SAP Commerce tenants sharing `_axfood_base.py`), `mathem_se`, `systembolaget_se`
(state alcohol monopoly), `kronansapotek_se` (pharmacy), `koro_se`,
`rekoekologiska_se`, plus the Eurostat electricity/gas/PPP fetchers.

| Candidate | URL | Outcome |
|---|---|---|
| Coop Sverige | https://www.coop.se/handla/ | **SHIPPED 2026-09-11 as `coop_se`** (scrapy_api). The co-operative chain — a third group, independent of the two Axfood tenants already onboarded, so its assortment and pricing are not redundant with them. It was listed in `known_blockers.md`'s "mechanically exhausted" bulk list; that verdict was wrong because the price API is a POST to a *different host* (`external.api.coop.se`, Azure APIM) gated on a public subscription key from the storefront JS bundle. 751 leaf categories; test run 129 rows; prices verified against the rendered page. |

**Gaps for the next run.** No `official_avg` source: SCB (Statistics Sweden)
publishes both a CPI and item-level average retail prices and neither is
onboarded — that is the highest-value unclaimed Swedish source and it is a
fetcher, not a spider. On the retail side ICA (the largest grocer by share) and
Lidl Sverige are untried here. Note that Lidl's *Bulgarian and Portuguese*
storefronts were confirmed price-free this pass (in-store assortment pages only,
JSON-LD `Offer` with no `price` key); check whether lidl.se differs before
spending budget on it.
