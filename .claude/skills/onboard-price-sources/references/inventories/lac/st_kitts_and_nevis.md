# St. Kitts and Nevis

_Inventory written: 2026-09-01_

Final F&B sweep, lac-agent-A. Cold start — no `lac/` inventory existed for this
country before this file. Before this pass: 0 sources total, 0 food. The country
spans two CaribeEats delivery-aggregator regions (`stkitts` and `nevis`, distinct
region IDs on backend.caribeeats.com) — both checked.

| Source name | URL | Channel | Status | Notes |
|---|---|---|---|---|
| RAMS St Kitts (CaribeEats listing) | https://backend.caribeeats.com/api/business/rams-st-kitts | supermarket | **SHIPPED** as `rams_stkitts` | See config YAML notes. 1013 real branded SKUs / 40 categories, XCD. |
| Valu Mart SK (CaribeEats listing) | https://backend.caribeeats.com/api/business/valu-mart-sk | — | **DEAD — empty catalog** | `categories: []`, 0 products, despite the plausible supermarket name. |
| Island Liquor (CaribeEats listing, St Kitts) | https://backend.caribeeats.com/api/business/island-liquor | specialty-food | **NOT PURSUED — RAMS is bigger and broader** | 117 SKUs / 4 categories, currency USD. Legitimate division-02 candidate for a future pass; deprioritized once RAMS St Kitts (1013 SKUs, food-led) shipped. Do not confuse with `island-liquor-dominica` — same brand family, different territory, different CaribeEats slug. |
| Gary Fruits & Flowers, ParisTaylor Boutique, Oomph Florals, Pure Water (CaribeEats "groceries" listings, St Kitts) | — | — | **NOT F&B-led / too narrow** | Florist/boutique businesses miscategorized under the platform's "Grocery & Retail" service tag; Pure Water is a single-category water distributor (11 SKUs, XCD) — legitimate but very narrow, not pursued given RAMS already ships. |
| CaribeShop Nevis (CaribeEats listing) | https://backend.caribeeats.com/api/business/caribeshop-nevis | supermarket / marketplace | **CANDIDATE, NOT SHIPPED — time budget** | 1166 SKUs / 57 categories, ~65% food-led by product count (Breakfast-Cereals, Canned/Jarred Goods, Snacks, Prepared Foods, Beverages, Fresh Fruits & Vegetables, Pasta, Dairy, Coffee, Frozen food & meats — vs. Pet Supplies/Personal Care/Cleaners minority). Messier than RAMS or CaribeShop GND (several single-item junk categories: "Test Category", "vehicle", "Takeout", "Restaurant delivery", "e-Cigs", "Rolling Paper" — looks manually curated and not well maintained, but the bulk of the catalog is real food SKUs). Payload's top-level `currency` read as USD in this probe; Nevis legally uses XCD like St Kitts, so re-verify at scaffold time rather than trusting the field blindly (unusual for this platform — every other business checked this pass reported the country's real currency). Ready to scaffold with the existing `_caribeeats_base.py` shared spider — just `SLUG = "caribeshop-nevis"`. |
| Massy Stores (main site, massystores.com) | https://www.massystores.com/ | — | **NOT APPLICABLE** | Massy Group does not operate a branch in St Kitts and Nevis (its Eastern Caribbean footprint is Barbados/Trinidad/Guyana/St Lucia/St Vincent — confirmed via WebSearch before the search budget was exhausted). |

## COICOP / channel gap after this pass

St. Kitts and Nevis ends at **1 source / 1 food** (`rams_stkitts`, supermarket,
food-led). No division-02-dedicated, pharmacy, or non-retail coverage yet.

Next agent: `caribeshop-nevis` (above) is the single best next candidate — same
shared spider, one new YAML, but double-check the currency field before trusting it
(this is the only CaribeEats business probed this pass whose payload currency
looked potentially wrong for its territory).
