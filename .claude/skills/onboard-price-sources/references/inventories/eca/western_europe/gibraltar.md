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

_Reviewed 2026-09-02_ (search-starved re-run). No re-search was spent here.
The Eroski reCAPTCHA Enterprise wall above is a genuine block confirmed
against three TLS profiles **and** a headless Playwright render, which
satisfies the skill's curl-AND-Playwright gate — it is not a curl-TLS false
negative and re-probing it would waste budget. Gibraltar stays at 0 sources.
Note for whoever picks this up: the Faroe Islands in this same run overturned
an identical-looking "nothing here" verdict purely by searching in the local
language. Gibraltar is English-speaking, so that particular lever does not
apply, but a Spanish-language query aimed at the La Línea / Campo de Gibraltar
cross-border shopping market is untried.
