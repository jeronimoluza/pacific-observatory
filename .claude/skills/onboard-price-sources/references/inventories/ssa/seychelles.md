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

---

## UPDATE 2026-09-01 (second pass) — WOW Delivery lead CLOSED as unscrapeable

The pass above named WOW Delivery as "the strongest lead for Seychelles and the
first thing the next pass should run down". It was run down. **It is a real
business with no website.**

A dedicated search returned only: a Facebook page (`/wowdeliverysey`), an
Instagram account (`@wow_delivery`), and a Google Play app
(`com.wowdeliveries.user`). One search result surfaced an indexed
`www.wowdeliverysey.com/about` URL, but that host **does not resolve** — DNS
NXDOMAIN on both `wowdeliverysey.com` and `www.wowdeliverysey.com` via
`curl_cffi` (chrome124 and safari17_0). The indexed URL is stale; the domain the
earlier pass guessed was right, and it is dead. Ordering is app- and
social-only.

Classify under `known_blockers.md` § "App-only / no scrapeable web catalogue".
Do not re-chase this lead without evidence the app's backend is reachable — that
would need an APK teardown, which is out of scope for a discovery pass.

Seychelles remains **0 sources**. The SPAR Seychelles thread from the pass above
is still unchased and is now the best remaining lead.
