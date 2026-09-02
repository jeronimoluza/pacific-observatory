# Seychelles

_Inventory written: 2026-09-01_

Final F&B sweep, wave (2026-09), agent B. Cold-start (no prior inventory file
existed). Seychelles had **zero** manifests of any kind before this pass (0
food, 0 total).

**Result: 0 sources shipped. No viable online grocery found.**

| Candidate | URL | Status | Notes |
|---|---|---|---|
| koek.sc | https://koek.sc | **DEAD — wrong vertical** | Search surfaced this as "Supermarkets in Seychelles" (a `/merchants/supermarket` directory page), but the live site (200, Next.js) is a **tour/boat-charter booking platform** (boats, tours, livecam) with no grocery or supermarket content at all — a false-positive match from a stale/mislabeled search snippet, not a marketplace directory worth following. |
| WOW Delivery | (contact only: wowdeliverysey@gmail.com, +2482611219) | **NOT PROBED — no domain found** | Described by `insideseychelles.com` as "Seychelles Number 1 Online Supermarket." Guessed domain `wowdeliverysey.com` does not resolve (NXDOMAIN). No working URL found this pass — this is the strongest lead for Seychelles and should be the first thing the next pass runs down (find the real domain, likely Facebook/Instagram-only ordering). |
| SPAR Seychelles (Eden Plaza, Eden Island) | spar-international.com/country/seychelles | **NOT PROBED — no e-commerce found** | SPAR operates physical stores in Seychelles per the SPAR International country page; no online ordering surfaced for the Seychelles operation specifically. |

No delivery marketplace (Jumia/Glovo/Bolt/Yango-style) operates in
Seychelles. Population is small (~100k) but wealthy/tourism-driven, so a
"no online grocery" verdict is less certain here than in Comoros/Eritrea —
record this as **unresolved, not structural absence**: the WOW Delivery lead
is real and worth a dedicated re-check.
