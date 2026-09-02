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
