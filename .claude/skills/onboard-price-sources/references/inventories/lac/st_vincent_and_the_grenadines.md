# St. Vincent and the Grenadines

_Inventory written: 2026-09-01_

Final F&B sweep, lac-agent-A. Cold start — no `lac/` inventory existed for this
country before this file. Before this pass: 0 sources total, 0 food.

| Source name | URL | Channel | Status | Notes |
|---|---|---|---|---|
| Massy Stores SVG (main brand site) | https://www.massystoressvg.com/ | — | **DEAD — brochure only, no shop** | Massy Group operates physical stores in Kingstown and Arnos Vale, but this domain is a static WordPress/AIOSEO corporate site with no WooCommerce shop route (`?rest_route=/wc/store/v1/products` returns `rest_no_route`). See `known_blockers.md` § "Brochure-only WordPress / no online store". Confirmed the `shopmassystores<code>.com` naming pattern used by the Barbados/Trinidad/St Lucia storefronts does NOT exist for SVG (`shopmassystoresvct.com`, `massystoresvct.com` both NXDOMAIN). |
| CaribeEats | https://backend.caribeeats.com/api/init | — | **NOT APPLICABLE** | Platform's region list (21 regions, confirmed via `/api/init`) does not include St Vincent/SVG/VCT under any spelling tried. |

**Examined but inconclusive beyond the above — not a confirmed "no online grocery"
finding.** The session's shared WebSearch budget (capped session-wide across all 12
parallel sweep agents) was exhausted before a fresh per-country search could be run
for St Vincent specifically. WebFetch against Bing/Google/DuckDuckGo search-results
URLs (attempted as a fallback) returned no usable result content — see
`st_martin_french_part.md` for the same tooling-constraint note, which applies
identically here.

## Recommendation for the next agent

Do not treat this as exhausted/negative. Re-run Phase 2 discovery with a working
WebSearch budget. St Vincent shares a retail ecosystem with the rest of the Eastern
Caribbean (Massy operates physical stores here, CK Greaves and other regional names
are plausible), so a fresh search plus the CaribeEats-style delivery-aggregator
pattern (which worked for Grenada/St Kitts/Nevis/Dominica) are the two highest-yield
next moves.
