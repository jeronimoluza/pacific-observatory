# Guinea-Bissau

_Inventory written: 2026-09-01_

SSA sweep, agent A. Country had only `wfp_prices` (shared regional HDX
fetcher) before this pass — 0 retail sources. **Result: 0 sources shipped.**
**This pass ran with zero WebSearch budget** (session-wide cap exhausted
before this country's turn) — every candidate below came from direct domain
probing and one WebFetch on a directory page, not a real search sweep.
Treat as a weak/partial pass; re-run Phase 2 with search access before
concluding Guinea-Bissau has no online grocery sector.

## Dead ends

| Candidate | URL | Status | Notes |
|---|---|---|---|
| Jumia | jumia.gw | **DEAD — Cloudflare challenge / no real storefront** | Same "Just a moment…" 403 pattern as jumia.td/jumia.cg; Jumia's active market list does not include Guinea-Bissau. |
| Casa Alberto (Bissau) | casaalberto.com | **DEAD — parked domain** | Resolves 200 but is a bare client-side redirect stub (`window.location.href="/lander"`), no content. |
| Kalliste Bissau | kalliste.gw | **NOT FOUND — NXDOMAIN** | |
| goafricaonline.com Guinea-Bissau directory | goafricaonline.com/gw, /gw/annuaire | **INCONCLUSIVE** | Both pages return HTTP 200 but the category/listing structure appears to be client-side rendered — no supermarket/food category links were recoverable from the static HTML via regex. Would need a JS-capable fetch to actually browse this directory; not attempted this pass. |
| Le Ninho Bissau, Bijagos supermercado | — | **NOT FOUND** | No resolvable domain found for either name; not chased via search (budget exhausted). |

**Conclusion:** No viable food-and-beverage retail source confirmed this
pass, but confidence is low given no real search ran. Re-check with fresh
WebSearch budget, particularly for Portuguese-language local terms
("supermercado Bissau online", "compras online Guiné-Bissau") which this
pass could not run.
