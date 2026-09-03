# Niger

_Inventory written: 2026-09-02_ (search-starved re-run; supersedes the
2026-09-01 zero-budget pass)

Before this pass: `wfp_prices` only, 0 retail sources. **Result: 0 shipped**,
but the French-language search the previous pass asked for did run and it
changed the picture: Niger has a real online-grocery sector, it is just not
reachable this pass.

## Candidates found (first real evidence for Niger)

| Candidate | URL | Status | Notes |
|---|---|---|---|
| e-Khumaisa Express Market | https://e-khumaisa.com/ | **NXDOMAIN** | Described in search results as an online market for Niger selling "produits alimentaires, boissons, hygiène" with home delivery in Niamey — precisely the source this country needs. The domain does not currently resolve. Either dead, renamed, or app-only. **The single highest-value lead for Niger**: worth one targeted search for a current domain or a Play Store listing next pass. |
| Direct GO | https://directresto.net/ | **LIVE, THIN** | 17KB page, no platform fingerprint, no price markup detected. Won Niger's 2021 e-Takara entrepreneurship prize (20M FCFA) for a grocery/errand-running service with mobile-money payment and tracked delivery. The domain name (`directresto`) suggests the live product is restaurant-led. Needs a Playwright trace to see whether a catalog exists behind the shell. |
| KAMES Express | https://www.kamesexpress.com/ | **LIVE, COURIER** | 22KB page, no price markup. Parcel courier with tracking and mobile-money/Visa payment — a logistics service, not a retailer. |
| Supermarché Azar | facebook.com/minimarketazar | **FACEBOOK-ONLY** | Real Niamey supermarket carrying local and imported European goods; no independent domain. |

## Dead ends (carried forward)

`jumia.ne` Cloudflare challenge, Niger not in Jumia's market list;
`scorene.com` expired/Namecheap parking; `baraka-niger.com`,
`leclubniamey.com`, `sonidep.ne` all NXDOMAIN.

## Next steps, in order

1. Find e-Khumaisa's current domain or app listing — it is a described,
   named, food-carrying online market and only its domain is missing.
2. Playwright trace on `directresto.net` to determine whether it has a
   grocery catalog or is restaurant-only.
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
