# Gambia, The

_Inventory written: 2026-09-01_

SSA sweep, agent A. Country had `fews_net` + `wfp_prices` (shared regional
humanitarian fetchers) before this pass — 0 retail sources. **Result: 0
sources shipped.** **This pass ran with zero WebSearch budget** (session-wide
cap exhausted before this country's turn) — every candidate below came from
direct domain probing only, no real search sweep ran at all for this
country. Treat this inventory as essentially unexamined; a proper Phase 2
pass with search access has not yet been run for The Gambia.

## Dead ends

| Candidate | URL | Status | Notes |
|---|---|---|---|
| Jumia | jumia.gm | **NOT FOUND — NXDOMAIN** | (Unlike Chad/Congo/Guinea-Bissau/Niger, this one doesn't even resolve to a squatted Cloudflare page.) |
| Glovo | glovoapp.com/gm/ | **DEAD — 404, no GM route** | |
| Yango | yango.com/en_int/ | **INCONCLUSIVE** | Landing page loaded but made no textual mention of Gambia; per-country URL list is client-side rendered and not recoverable from static HTML. Does not confirm absence. |
| Home Front Gambia | homefrontgambia.com | **NOT FOUND — NXDOMAIN** | |
| Kombo Supermarket | kombosupermarket.gm | **NOT FOUND — NXDOMAIN** | |

**Conclusion:** No candidates confirmed either way. This is the weakest
inventory in this pass — essentially no real discovery work was possible
without WebSearch. The next pass should start Gambia from scratch with a
proper English-language search (Gambia is anglophone, so this is a
comparatively low-cost re-run) rather than trusting these dead ends.
