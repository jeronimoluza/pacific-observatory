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

---

## UPDATE 2026-09-11 (food-sourcing pass) — TWO FOOD SOURCES SHIPPED

Monaco is no longer a food-source-zero country. **Result: 2 shipped
(obba_mc, vinalia_mc), both genuinely Monaco-domiciled specialty-food
retailers found via French-language search for épicerie fine / cave à vin
rather than supermarkets.**

| Source | URL | Channel | Status | Notes |
|---|---|---|---|---|
| `obba_mc` | https://www.obba.mc/ | specialty-food | **SHIPPED — 37 rows in a --max-items 20 test, all distinct urls/ids, 0 zero-price, 100% EUR** | Fine grocery / butcher / fishmonger ("Wagyu & Produits d'exception"). Domicile confirmed: /contact/ gives "La Panorama, 57 rue Grimaldi 98000 Monaco". WooCommerce; Store API 500s (broken plugin, confirmed 3 request variants), so scrapes the server-rendered shop-loop HTML instead (standard `li.product` / `woocommerce-loop-product__title` / `woocommerce-Price-amount` markup). Covers meat, fish/seafood, wine/spirits, ice cream. |
| `vinalia_mc` | https://www.vinalia.mc/ | specialty-food | **SHIPPED — 95 rows in a --max-items 20 test, all distinct urls/ids, 0 zero-price, 100% EUR** | Wine/champagne/spirits/épicerie fine, 718 products across 65 categories. Domicile confirmed via +377 (Monaco country code) phone number. Odoo 17 website_sale; `/shop`'s own pager is broken and hidden by custom CSS, so the spider seeds all 65 category URLs and follows each category's own (CSS-hidden but HTML-present) `/page/N` links. Covers charcuterie, tinned fish, sauces/oils, chocolate, honey alongside wine. |

Both sidestep the France/Monaco shared-platform duplication question below
by being their own standalone platform instances (Odoo / WooCommerce on a
`.mc` domain with Monaco-specific evidence), not a shared national chain
deployment.

## Candidates checked and rejected this pass

| Candidate | What | Why not shipped |
|---|---|---|
| `marche-u.mc` | Système U's own `.mc` storefront, genuinely Monaco-domiciled (7 bd d'Italie) | Brochure/showcase only — `/nos-rayons/*` department pages carry zero price tokens and zero cart mentions. Resolves the France/Monaco domain-ownership question for THIS domain (it's not the shared coursesu.com platform) but there is no online ordering to onboard. |
| `delovery.mc` | Genuine `.mc` food-delivery platform | Re-probed per standing instruction to retry Cloudflare blocks — still 403 on chrome124/chrome120/safari17_0. Verdict unchanged. |
| `mrroomservice.mc` | Curated multi-shop concierge delivery (foie gras, caviar, wine, Dean & DeLuca) | No platform fingerprint matched; shop pages render zero price tokens server-side (client-rendered). Needs a Playwright network trace, not attempted — OBBA/Vinalia already filled the slot. |
| `mitronbakery-monaco.com` | Bakery with an "EPICERIE-FINE & BOUTIQUE" order page | Wix site; "ecwid" homepage hits are Wix's own storefront-widget self-reference (same false-fingerprint pattern as neufeldhof_li), not a real Ecwid store. Category page renders zero prices server-side. |

**The France/Monaco shared-platform policy question remains OPEN and
deliberately unanswered** (courses.monoprix.fr, Carrefour Market Monaco's
drive page, coursesu.com/drive-marcheu-monaco) — moot for this pass since
two genuinely Monaco-domiciled sources now exist, but still unresolved for
a future pass that might want the bigger French-chain catalogs.
