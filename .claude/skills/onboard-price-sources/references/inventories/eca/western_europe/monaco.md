# Monaco — price source inventory (eca/western_europe/monaco)

_Inventory written: 2026-09-01_ (ECA F&B sweep, agent A)

Started at 0 sources of any kind. **Result: 0 shipped -- deliberately not
onboarded, policy question flagged rather than a search miss.**

## What was found

Monaco's grocery retail (Carrefour Market Monaco, Monoprix) runs entirely
on the same national French e-commerce platforms that serve all of France
-- `courses.monoprix.fr` (200, 754KB, no anti-bot signals detected) and
Carrefour's French storefront. No Monaco-registered domain exists:
`carrefour.mc`, `monoprix.mc`, `spar.mc` all fail DNS resolution.
`casino.mc` resolves but is the unrelated Casino de Monte-Carlo gambling
site (Société des Bains de Mer), not the French "Casino" supermarket
chain -- a false-lead trap worth recording so a future pass doesn't
re-walk it.

## Why this was NOT shipped

`courses.monoprix.fr` is a French-national platform/catalogue, not a
Monaco-specific legal entity or price list. Onboarding it under
`eca/western_europe/monaco/` risks exact duplication if a future France
onboarding pass independently builds the same domain as `monoprix_fr` --
the identical catalog and prices would then be double-counted under two
country labels, contaminating any cross-country comparison the same way
the policy-tracker cross-country-contamination pattern does elsewhere in
this codebase.

This is a genuine open question, not a resolved "skip": does a shared
cross-border national platform count as valid coverage for a
micro-territory it physically delivers to (Monaco is a customs union
member with France and uses French postal codes), and if so, under which
country label -- Monaco, France, or both with a shared-source
cross-reference? Flagging for the orchestrator/a future pass to decide
rather than making that call unilaterally mid-sweep.

## Next steps for a future pass

- If the policy question above is resolved in favor of shipping, note
  that `courses.monoprix.fr` was NOT platform-fingerprinted or
  probe-tiered this pass (no anti-bot signals in a first-look 200
  response is as far as it got) -- full Phase 3 probing would still be
  needed.
- No Monaco-specific storefront exists to search for further; any future
  pass should focus on the France/Monaco shared-platform policy question
  rather than re-searching for a domain that doesn't exist.

---

## Update 2026-09-01 (Tier-1 greenfield pass) — SOURCE SHIPPED

Monaco is no longer a zero-source country. **The open policy question below is
still open and was deliberately NOT answered** — the source shipped sidesteps it.

| Source | URL | Channel | Status | Notes |
|---|---|---|---|---|
| Boutique ACM | https://boutiqueacm.com/ | fashion | **SHIPPED — `boutiqueacm_mc`, 96 rows** | Official shop of the Automobile Club de Monaco, the Monégasque institution that organises the Monaco Grand Prix. Open, unauthenticated WooCommerce Store API; 122 products, EUR at currency_minor_unit=2. Non-food (GP apparel and merchandise) — shipped because a Monaco-domiciled source with real prices beats no source, and because no France pass would ever build this domain, so there is zero duplication exposure. |
| Delovery | https://delovery.mc/ | — | **BLOCKED — Cloudflare strict** | A genuine `.mc` Monaco-domiciled food delivery platform, and the best food lead the territory has. 403 on chrome124, chrome120, chrome99 AND safari17_0 — all four TLS profiles per the mandatory gate, so not a curl-TLS false negative. Blocked, not absent. Worth a retry if anti-bot posture ever changes. |
| houra.fr / carrefour.fr / courses.monoprix.fr | — | — | **POLICY QUESTION, unresolved** | French national platforms that deliver to Monaco. See below. |

**The policy question is unchanged and still the user's to decide:** does a shared
French national platform count as Monaco coverage, and under which country label?
Onboarding one risks exact duplication against a future France pass building the
same domain, double-counting an identical catalogue under two country labels.
Shipping Boutique ACM removes the *urgency* of that decision (Monaco is no longer
at zero) but does not answer it — Monaco still has no food source.

**Confirmed absences (do not re-search):** `carrefour.mc`, `monoprix.mc` and
`spar.mc` all fail DNS resolution. `casino.mc` resolves but is the Société des
Bains de Mer casino, not the French Casino supermarket chain.
