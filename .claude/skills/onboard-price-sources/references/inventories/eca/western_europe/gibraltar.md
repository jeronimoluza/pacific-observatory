# Gibraltar — price source inventory (eca/western_europe/gibraltar)

_Inventory written: 2026-09-01_ (ECA F&B sweep, agent A)

Started at 0 sources of any kind. **Result: 0 shipped -- the one real
candidate is genuinely blocked, not a search miss.**

## Dead end: Eroski City / Eroski Center (www.eroski.gi)

Eroski is Gibraltar's only supermarket chain confirmed to offer home
delivery (Morrisons, the other UK-chain branch present, explicitly does
not). `www.eroski.gi` serves `<title>Checking your browser -
reCAPTCHA</title>` on `curl_cffi` across `chrome124`, `chrome120`, AND
`chrome99` (all three TLS profiles, per the mandatory gate), and the
challenge does not clear after a full headless-Playwright render with an
8-second wait either -- genuine block, not a curl-TLS false negative. Full
write-up under "Google reCAPTCHA Enterprise" in `known_blockers.md`.

## Considered and rejected: Hungry Monkey (hungrymonkey.gi)

A Preoday-platform mobile ordering app (`order.hungrymonkey.gi`,
`com.preoday.mobile.hungrymonkey` on the Play Store). This is a
restaurant-food delivery aggregator, not a grocery retailer -- does not
satisfy the win criteria's channel enum (supermarket / hypermarket /
convenience / fresh-market / specialty-food / marketplace-as-directory).
Not pursued further.

## Next steps for a future pass

- Eroski's block is a genuine reCAPTCHA Enterprise wall (not a
  TLS-fingerprint false positive) -- would need a captcha-solving service
  to progress, out of scope for routine onboarding.
- No other grocery e-commerce candidate was found for Gibraltar this
  pass; worth a fresh WebSearch pass in a future wave for anything new
  (e.g. a Wolt/Glovo-style marketplace entering the territory).

---

## Update 2026-09-01 (Tier-1 greenfield pass) — SOURCE SHIPPED

Gibraltar is no longer a zero-source country.

| Source | URL | Channel | Status | Notes |
|---|---|---|---|---|
| Sosi's Vege | https://www.sosisvege.com/ | specialty-food | **SHIPPED — `sosisvege_gi`, 180 rows** | Gibraltar-domiciled greengrocer importing Moroccan produce. Domicile proven from the site's own schema.org PostalAddress: 18 Parliament Lane, Gibraltar, GX11 1AA, addressCountry "GI". site123 platform, Tier 1A, no anti-bot. 15 categories; food-weighted (main groceries 44, vegetables 43, fruit 34, spices 12, nuts 10). Prices GIP. **Do not add pagination** — the site accepts `?page=` but ignores it and re-serves page 1 byte-for-byte. |
| Ramsons | https://order.ramsons.gi/ | — | **DEAD — app-only** | Gibraltar supermarket since 1975 and the territory's most promising grocery lead. `order.ramsons.gi` serves "Ramsons Supermarket - Web Ordering Coming Soon"; ordering is iOS/Android only. Worth re-checking in a future wave — the web storefront is announced, not absent. |
| NomNoms | https://www.nomnoms.gi/ | — | **NOT APPLICABLE** | Restaurant food-ordering and booking aggregator, not a grocer. |
| Eroski | https://www.eroski.gi/ | — | **BLOCKED (verdict unchanged)** | reCAPTCHA Enterprise wall confirmed by the earlier pass across three TLS profiles AND headless Playwright. Not re-probed. Separately note `eroski.gi` fronts Eroski's Spanish storefront, so even if unblocked its prices would be Spanish shelf prices in EUR, not Gibraltarian — the same definitional problem Monaco has. |

**Lesson:** the earlier pass searched only for supermarkets and found one blocked
chain. Widening to any Gibraltar-domiciled food retailer found a shippable source
on the first search. A greengrocer is not a supermarket, and the bar for a
zero-source country is "a real priced catalogue", not "a full-range grocer".
