# Comoros

_Inventory written: 2026-09-01_

Final F&B sweep, wave (2026-09), agent B. Cold-start (no prior inventory file
existed). Comoros had **zero** manifests of any kind before this pass (0 food,
0 total). Search-budget-limited pass (WebSearch quota was shared/exhausted
mid-sweep across the 12 parallel agents) — one round of marketplace/local
search plus direct-domain probing.

**Result: 0 sources shipped. No viable online grocery found.**

| Candidate | URL | Status | Notes |
|---|---|---|---|
| Comores Market | https://comoresmarket.com | **DEAD — broken TLS / 404** | Search results describe it as an "online supermarket drive" (order + 1hr pickup) for Moroni. Live probe 2026-09-01: HTTPS fails with `TLSV1_ALERT_INTERNAL_ERROR` across chrome124/chrome120/chrome99/safari17_0 impersonation profiles (server-side TLS misconfiguration, not a WAF — no handshake completes at all); plain HTTP on the bare domain returns 404. The business may exist (Facebook page is active) but has no working website to scrape. Re-check in ~6 months in case the site is fixed. |
| Smart Shahula, MAG MARKET, SAWA Prix, SARA MARKET | (no domains found) | **NOT PROBED — no web presence found** | Physical supermarkets in Moroni surfaced by search (via `evendo.com` listing aggregator, not their own sites); no independent e-commerce domain found for any of them in this pass. |

No marketplace-directory candidate (Jumia/Glovo/Bolt Food/Yango-style) was
found operating in Comoros. Population (~850k) and general SSA e-commerce
patterns make a thin market plausible; this is a "no online grocery sector
found," not a confirmed structural absence — worth a fresh, deeper pass
(French-language search specifically) rather than treating as settled.
