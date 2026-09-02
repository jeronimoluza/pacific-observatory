# Faroe Islands — price source inventory (eca/western_europe/faroe_islands)

_Inventory written: 2026-09-02_ (search-starved re-run; supersedes the
2026-09-01 pass)

Before this pass: 0 sources of any kind. **Result: 2 shipped.**

## The previous conclusion was wrong, and the reason is worth remembering

The 2026-09-01 file concluded "no online grocery sector currently exists in
this market" after probing SMS, Bónus, Miklagarður, Wolt and Bolt. It also
noted, correctly, that its WebSearch budget had run out and that a future pass
should **search in Faroese** (`dagligvøru`, `handlan`, `netbúð`) rather than
guess domains.

That Faroese-language search was run this pass and immediately surfaced live
e-commerce the English/domain-guess pass could not see. The lesson is the one
the skill already states and this is a clean confirmation of it: **an
English-only or domain-guess pass in a small non-English market produces false
negatives, not findings.**

## Shipped

| Source name | URL | Channel / role | Status | Notes |
|---|---|---|---|---|
| `alvaro_fo` | https://www.alvaro.fo/ | fashion / `retailer_sku` | **SHIPPED** | Tórshavn retailer, free delivery and same-day delivery in Tórshavn/Hoyvík/Argir. Shopify, `/products.json` open, page 2 returns a different set. Test run scraped **690 items**; DKK 549.95 winter boots — sane. Catalog is clothing and footwear, so `channel: fashion`. |
| `djor_fo` | https://djor.fo/ | pet / `retailer_sku` | **SHIPPED** | Djórahandilin, the islands' largest animal-goods retailer. WooCommerce Store API open with **191 categories**; reports DKK with `currency_minor_unit: 2` (19900 → 199.00), which the shared base divides out. Test run scraped 100 items (DKK 199.00 salmon oil). |

Neither is a food channel. They are onboarded because the country had **zero**
sources of any kind, and under the "take whatever verifies" rule for
low-coverage countries every division is a gap.

## Still no food retail — that part of the old finding holds

| Candidate | URL | Status | Notes |
|---|---|---|---|
| SMS (Bónus + Miklagarður group) | https://www.sms.fo/keyp/ | **NO GROCERY CATALOG** | Re-probed: WooCommerce markers present but the transactable surface is still gift cards, not groceries. |
| Bónus | bonus.fo | **FLYER SITE** | Carried forward: no e-commerce platform fingerprint, no add-to-cart. |
| Miklagarður | miklagardur.fo | **WIX GIFT CARD** | Carried forward: `/keyp` is a Wix-Stores gift-card page. |
| Stokholm | https://stokholm.fo/ | **reCAPTCHA / Cloudflare wall** | New this pass: HTTP 403, "Checking your browser". Not re-probed past that. |
| Netkeyp | netkeyp.fo | **NXDOMAIN** | Referenced by a WordPress blog; the domain itself does not resolve. |
| Wolt / Bolt Food | — | **NO FAROESE COVERAGE** | Carried forward: `wolt.com/fo` redirects to the global homepage; `bolt.eu/.../torshavn/` 404s. |

## Next steps

- A further Faroese-language search aimed specifically at grocery terms is the
  obvious follow-up; this pass spent one query and got two non-food sources
  out of it, which suggests the market is under-searched rather than empty.
- `stokholm.fo` sits behind a challenge and was not resolved either way.
