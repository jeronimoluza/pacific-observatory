# Congo, Rep. (Congo-Brazzaville)

_Inventory written: 2026-09-01_

SSA sweep, agent A. Country had only `wfp_prices` (shared regional HDX
fetcher) before this pass — 0 retail sources. **Result: 0 sources shipped.**
**This pass ran with zero WebSearch budget** (the session-wide cap was
exhausted before this country's turn) — every candidate below was found via
direct domain probing (`curl_cffi impersonate=chrome124`) and WebFetch on
directory/search-engine pages, not a real search sweep. Treat this inventory
as a weak/partial pass, not an exhaustive one — a future run with search
budget should redo Phase 2 properly before concluding Congo-Brazzaville has
no online grocery sector.

## Dead ends

| Candidate | URL | Status | Notes |
|---|---|---|---|
| Jumia | jumia.cg | **DEAD — Cloudflare challenge / no real storefront** | Returns a Cloudflare "Just a moment…" page (403), consistent with a squatted/reserved domain rather than live Jumia infrastructure — Jumia's current active market list does not include Congo-Brazzaville. |
| Glovo | glovoapp.com/cg/ | **DEAD — 404, no CG route** | |
| "Douka" (grocery-delivery app, named in the task brief as a lead worth checking) | douka.cg, doukacongo.com, douka-congo.com, douka.app, mydouka.com | **NOT CONFIRMED TO EXIST** | None of the guessed domains resolve (NXDOMAIN). A Google Play Store search for "douka congo" surfaced no matching app (returned unrelated results: Congo Travel, Congo Ndaku, Congosa, Congo Easy). This candidate could not be verified without WebSearch and should be re-checked properly next pass rather than assumed real or assumed dead. |
| Congo Easy (delivery app) | congoeasy.com | **UNREACHABLE this pass** | HTTP 509 (bandwidth exceeded) on the one probe attempt; not retried. Play Store listing exists ("Jj Group Company") but scope (courier vs. grocery) not confirmed. |
| Congosa | — | **NOT PURSUED — appears to be a taxi/parcel courier app, not grocery retail** | Surfaced only via the Play Store search snippet above; not independently probed. |
| Simba Supermarché | simbasupermarche.cg, simba.cg | **NOT FOUND** | Neither guessed domain resolves. |

**Conclusion:** No viable food-and-beverage retail source confirmed this
pass. Unlike Chad/Guinea-Bissau/Niger/Gambia/Liberia below, this country's
dead ends are especially weak evidence (zero real search queries ran) — the
"Douka" lead in particular is unresolved, not disproven.
