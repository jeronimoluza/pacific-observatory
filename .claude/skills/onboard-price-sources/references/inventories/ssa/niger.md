# Niger

_Inventory written: 2026-09-01_

SSA sweep, agent A. Country had only `wfp_prices` (shared regional HDX
fetcher) before this pass — 0 retail sources. **Result: 0 sources shipped.**
**This pass ran with zero WebSearch budget** (session-wide cap exhausted
before this country's turn) — every candidate below came from direct domain
probing only. Treat as a weak/partial pass; re-run Phase 2 with search
access before concluding Niger has no online grocery sector.

## Dead ends

| Candidate | URL | Status | Notes |
|---|---|---|---|
| Jumia | jumia.ne | **DEAD — Cloudflare challenge / no real storefront** | Same "Just a moment…" 403 pattern seen across Chad/Congo/Guinea-Bissau; Jumia's active market list does not include Niger. |
| "Scorène" (guessed supermarket-chain domain) | scorene.com | **DEAD — expired domain, Namecheap parking page** | Resolves 200 but is a Namecheap "domain registration has expired" market-listing page, not a live business. |
| Baraka Niamey supermarché | baraka-niger.com | **NOT FOUND — NXDOMAIN** | |
| SONIDEP (fuel/gov entity, checked opportunistically) | sonidep.ne | **NOT FOUND — NXDOMAIN** | Not a food source in any case; checked only as a general `.ne` domain liveness probe. |
| Le Club Niamey | leclubniamey.com | **NOT FOUND — NXDOMAIN** | |

**Conclusion:** No viable food-and-beverage retail source confirmed this
pass, but confidence is low given no real search ran. Re-check with fresh
WebSearch budget for French-language queries ("supermarché Niamey en
ligne", "livraison courses Niamey") which this pass could not run.
