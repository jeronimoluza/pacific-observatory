# Eritrea

_Inventory written: 2026-09-01_

Final F&B sweep, wave (2026-09), agent B. Cold-start (no prior inventory file
existed). Eritrea had **zero** manifests of any kind before this pass (0
food, 0 total).

**Result: 0 sources shipped. No viable online grocery found.**

| Candidate | URL | Status | Notes |
|---|---|---|---|
| Asbeza | Google Play `com.ecwid.ShopAt.Asbeza` | **DEAD — domain squatted/parked** | App listing shows it's built on Ecwid (a hosted storefront SaaS). Direct-guessed `asbeza.com` resolves but serves a domain-parking/consent-manager landing page (no product markup, no mention of Ecwid, no title) — not the real storefront. The actual Ecwid subdomain or custom domain was not found (WebSearch quota was exhausted session-wide before it could be searched properly — this is a gap to close on the next pass, not a confirmed dead end for the app itself). |
| Day-To-Day Discount, Family Supermarket (Asmara) | (no domains found) | **NOT PROBED — no web presence found** | Physical grocery stores surfaced via `evendo.com`/`goafricaonline.com` directory listings; no independent e-commerce presence found. |

No delivery marketplace (Jumia/Glovo/Bolt/Yango-style) operates in Eritrea —
none of the usual pan-African aggregators list the country. This is
consistent with Eritrea's structurally isolated internet/telecom sector
(single state-run ISP, very low penetration) rather than a search gap: prior
knowledge strongly suggests there is no functioning online retail sector
inside the country. Treat as a likely **structural absence**, but the Asbeza
app is an open thread — worth one more WebSearch-budget pass specifically to
find its real domain before writing this off completely.
