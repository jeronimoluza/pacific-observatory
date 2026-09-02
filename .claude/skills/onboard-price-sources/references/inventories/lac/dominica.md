# Dominica

_Inventory written: 2026-09-01_

Final F&B sweep, lac-agent-A. Cold start — no `lac/` inventory existed for Dominica
before this file. Before this pass: 1 source total (`tropicart_dm`, marketplace,
already covers other-retail), 0 food. CaribeEats splits Dominica into two delivery
regions on its own platform, `roseau-dominica` and `portsmouth-dominica` — the
Portsmouth region returned only 1 grocery-tagged business (not investigated, small
town, low expected yield); Roseau (the capital) returned 2.

| Source name | URL | Channel | Status | Notes |
|---|---|---|---|---|
| Island Liquor Dominica (CaribeEats listing) | https://backend.caribeeats.com/api/business/island-liquor-dominica | specialty-food | **SHIPPED** as `island_liquor_dm` | See config YAML notes. 42 SKUs / 7 categories, 100% alcohol+tobacco (division 02), XCD. |
| CaribeShop DM (CaribeEats listing) | https://backend.caribeeats.com/api/business/caribeshop-dm | — | **REJECTED — not food-led** | 6206 SKUs / 15 categories, but "Foods & Beverages" is only 483 of 6206 (~8%) — the catalogue is dominated by Personal Care (3544), OTC (825), Household (341), Beauty & Health (365). By far the largest catalog found this pass on any platform, but fails the food-and-beverage-lead criterion for THIS sweep. A future pharmacy/general-retail-scoped pass should revisit this — it is a large, real, XCD-priced… actually payload `currency` read as **USD** for this business specifically (double-check at scaffold time, same caveat as `caribeshop-nevis` in the St. Kitts and Nevis file). |
| (Portsmouth region, 1 grocery-tagged business) | — | — | **NOT INVESTIGATED — time budget** | Small secondary town; not probed this pass given Roseau already yielded a shippable source. |

## COICOP / channel gap after this pass

Dominica ends at **2 sources / 1 food** (`island_liquor_dm`, specialty-food, narrow
division 02; `tropicart_dm` remains other-retail/marketplace, not counted as food).
No supermarket/hypermarket/fresh-market coverage exists yet — CaribeShop DM (above)
is the only lead found and it fails the food-lead bar for an F&B-scoped source. The
Portsmouth CaribeEats region and a fresh general per-country search (not run this
pass — WebSearch budget was exhausted mid-sweep, see `st_martin_french_part.md` and
`st_vincent_and_the_grenadines.md` for the same constraint) are the next things to
try.
