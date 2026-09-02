# Nigeria

_Inventory written: 2026-09-01_

Wave 9 pass, cold-start (no workbook candidates — confirmed by reading
`outputs/sources_pending_jero.xlsx` directly: Nigeria appears only in the "NO CANDIDATES -
discovery" sheet, `retailer_sources_now=2`, `any_sources_now=2`, `sources_needed_to_reach_5=3`
as of when that workbook was built). Already-covered before this pass: `hoursmarket_ng`
(supermarket), `supermart_ng` (supermarket), `nbs_selected_food` (official_avg, source_key
`nbs_ng_food`), `wfp_prices` (official_avg) — 4 sources / 2 food. This pass needed exactly 1
more source of any channel; target was >=5 sources AND >=2 food. The food requirement was
already met, so no retail/food candidate below was pushed past a quick liveness probe.

| Source name | URL | Channel | Status | Notes |
|---|---|---|---|---|
| NBS "CPI and Inflation Report" | https://nigerianstat.gov.ng/elibrary?queries%5Bsearch%5D=CPI+and+Inflation+Report | `null` (cpi_benchmark) | **SHIPPED** as `nbs_ng_cpi` | Confirmed first, per the brief, that `nbs_selected_food.py` (source_key `nbs_ng_food`) emits only PriceObservation rows (item-level average retail prices) and no index rows — this is a genuine complement, not a duplicate. Monthly XLSX (base Nov2009=100), Table2 sheet, discovered dynamically via the same elibrary-search pattern as `nbs_ng_food` (no stable per-month URL). Same ~21-month elibrary staleness as the food series: newest edition on the public catalog is October 2024 (doc id 1241583) as of 2026-09-01, despite NBS's internal release-schedule widget listing editions through late 2026 — shipped anyway since discovery is dynamic and will self-heal if NBS resumes uploading. Two publisher data-quality gotchas hit and fixed: (1) month-name column mixes 3-letter and full-name spellings inconsistently within the same year; (2) the January row for the newest year (Jan 2024) ships with a blank year cell, unlike every earlier January back to 1995 — a naive forward-fill silently drops the whole most-recent year. Verified via `po prices collect --source nbs_ng_cpi`: 972 rows (81 months, Feb 2018 - Oct 2024, none missing, x 12 divisions), zero nulls/zero/negative index values, idempotent re-run (0 new rows, cutoff correctly advanced from the written CSV), 3 divisions hand-cross-checked against the raw XLSX cell values (exact match). |
| Jumia Nigeria | https://www.jumia.com.ng/ | marketplace | **DEAD — Cloudflare challenge** | HTTP 403 `<title>Just a moment...</title>`, `cf-mitigated: challenge`, on `curl_cffi` chrome124/chrome120/safari17_0 alike. Matches the exact signature already recorded for `jumia.com.gh` and `jumia.ma` in `known_blockers.md` — a shared Cloudflare tenant across Jumia's African storefronts. No `jumia_*` spider exists anywhere in this repo to reuse. |
| Glo (gloworld.com) | https://www.gloworld.com/ | — (would be `tariff`) | **DEAD — Cloudflare challenge** | Same signature as Jumia NG: HTTP 403 `Just a moment...`, `cf-mitigated: challenge`, fails all 3 curl_cffi profiles. |
| PPPRA (pppra.gov.ng) | https://pppra.gov.ng/ | — (would be `tariff`, fuel, coicop_codes: ["07.2.2"]) | **DEAD — unreachable, likely defunct agency** | `curl_cffi` times out (curl error 28) at both 20s and 45s; DNS resolves fine against `8.8.8.8` (41.222.211.183), so this is a real TCP-level dead host, not a sandbox DNS lie. PPPRA (Petroleum Products Pricing Regulatory Agency) was folded into NMDPRA (Nigerian Midstream and Downstream Petroleum Regulatory Authority) around 2021 — consistent with an abandoned host. |
| NMDPRA (nmdpra.gov.ng) | https://nmdpra.gov.ng/ | — (would be `tariff`, fuel) | **NOT PROBED PAST LIVENESS — real lead for next pass** | Live (200, 26KB) on first touch, unlike its PPPRA predecessor. This is the current regulator for downstream petroleum pricing in Nigeria and the likely correct target for the brief's "NNPC / PPPRA fuel prices" lead — not pursued further this pass because the 1-source target was already cleared by the CPI build. |
| NERC (nerc.gov.ng) | https://nerc.gov.ng/ | — (would be `tariff`, electricity, MYTO orders) | **NOT PROBED PAST LIVENESS — real lead for next pass** | Live (200, 179KB) on first touch. MYTO tariff orders are typically PDF; page structure not yet examined. |
| Shoprite Nigeria (shoprite.com.ng) | https://www.shoprite.com.ng/ | — | **DEAD — unreachable** | `curl_cffi` times out (curl error 28) at both 20s and 45s; DNS resolves fine against `8.8.8.8` (178.79.178.218). Consistent with the brief's own note and with the already-documented Shoprite Mozambique/Lesotho pattern (regional retreat) — worth a re-check in a future wave rather than assuming permanently dead, since this one didn't even reach the shared `shopriteafrica` AEM corporate portal that MZ/LS resolve to (a straight connection timeout, not a served corporate page). |
| SPAR Nigeria (sparnigeria.com) | https://www.sparnigeria.com/ | would be `supermarket` | **NOT PROBED PAST LIVENESS — real lead for next pass** | Live (200, 169KB) on first touch. Not pursued further this pass; genuine food-channel candidate for a future wave if Nigeria's food-source count ever needs widening beyond the current 2. |
| Konga (konga.com) | https://www.konga.com/ | marketplace | **NOT PROBED PAST LIVENESS** | Live (200, 625KB), no WAF on the homepage. Marketplace — per skill doctrine the correct approach would be its seller directory, not its own catalog; not investigated further this pass. |
| MTN Nigeria (mtn.ng) | https://www.mtn.ng/ | — (would be `tariff`) | **NOT PROBED PAST LIVENESS** | Live (200, 4.3MB — heavy page). Not pursued; target already cleared. |
| Airtel Nigeria (airtel.ng) | https://www.airtel.ng/ | — (would be `tariff`) | **NOT PROBED PAST LIVENESS** | Live (200, 7KB — likely a redirect/stub page, would need a deeper look). Not pursued; target already cleared. |
| PricePally (pricepally.com) | https://pricepally.com/ | would be `supermarket`/`marketplace` | **NOT PROBED PAST LIVENESS** | Live (200, 67KB). Not pursued; target already cleared. |
| Ebeano Supermarket (ebeanosupermarket.com) | https://ebeanosupermarket.com/ | would be `supermarket` | **NOT PROBED PAST LIVENESS — real lead for next pass** | Live (200, 133KB) once the TLS cert/SNI mismatch on the bare hostname is worked around (`curl_cffi` needs `verify=False` or the exact SNI the cert expects — a client-side quirk, not a WAF). The brief's suggested `ebeano.ng`/`www.ebeanosupermarket.com` guesses both fail (wrong domain / cert-name mismatch respectively); the bare `ebeanosupermarket.com` apex is the one that resolves and serves content. Not pursued further this pass. |
| Marketsquare (marketsquare.ng) | https://marketsquare.ng/ | — | **DEAD — parked/misconfigured, not the retailer** | Resolves and returns HTTP 200, but serves a bare Apache/nginx-style directory autoindex listing ("Index of /"), not the Marketsquare storefront. Genuinely not the site the brief meant — the real Marketsquare Nigeria domain (if different from `.ng`) was not searched for, to stay within budget once the target was already met. |

## COICOP / channel gap after this pass

Nigeria sits at 5 sources / 2 food after this pass: `hoursmarket_ng` and `supermart_ng`
(both `supermarket`, retailer_sku) carry the food/beverage weight; `nbs_ng_food` and `wfp_prices`
are `official_avg`; the new `nbs_ng_cpi` is `cpi_benchmark`, covering COICOP divisions 01-12 as
an index series (no division 13 breakout — folded into division 12 in NBS's own legacy
12-group scheme). No `tariff` source exists yet for Nigeria — NMDPRA (fuel) and NERC
(electricity) are both confirmed live and are the cheapest next builds if Nigeria's source
count needs padding again in a future wave. Retail food coverage beyond the existing two
supermarkets is thin; SPAR Nigeria and Ebeano Supermarket are both live and worth a real Phase
3 probe (tier classification, platform fingerprint) before anything else on this list, since
neither showed a WAF on first touch.
