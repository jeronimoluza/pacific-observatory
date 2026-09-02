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

## Common Crawl coverage

Probed 2026-09-02 by the common_crawl session: 8 crawls spanning 2019-2026,
`max_blocks=40`. Counts are host records in the CC index and, separately, the
subset matching the manifest's `archive_path_re`.

| Source | Crawls with host | Host records | Matching PDP regex | Verdict |
|---|---|---|---|---|
| `alvaro_fo` (Shopify `/products.json`) | 7/8 | 3572 | 1686 | Strong series. |
| `djor_fo` (WooCommerce Store API) | 6/8 | 267 | 6 | **In CC, but PDPs not archived** — see note below. |

**djor_fo: the regex is correct; CC simply did not archive its PDPs.** 267 host
records across 6 crawls, but only 6 match `^/product/[^/?]+`. Resolved
2026-09-02 by dumping the distinct archived paths rather than guessing from the
counts — in the WooCommerce era CC archives djor.fo's *category tree*, not its
products:

| Crawl | Records | `/product-category/*` | `/product-brands/*` | `/product/<slug>` |
|---|---:|---:|---:|---:|
| CC-MAIN-2023-14 | 57 | 49 | 1 | 2 |
| CC-MAIN-2024-46 | 42 | 32 | 1 | 2 |
| CC-MAIN-2025-21 | 40 | 29 | 5 | 2 |
| CC-MAIN-2026-25 | 35 | 27 | 5 | 0 |

Roughly two PDPs per crawl; the 6 matches are all the PDPs CC holds. The live
site does serve `/product/<slug>/` (confirmed against the 2,159 rows scraped
2026-09-02), so the live pattern and the archive simply disagree about what was
*crawled*, not about what the URLs are.

Two hypotheses were tested and rejected:

- **A migrated permalink base.** `/shop` appears in exactly one crawl
  (CC-MAIN-2024-46, 5 records) and resolves to a single bare `/shop/` — no
  `/shop/<slug>` family ever existed. Widening to `^/(product|shop)/[^/?]+`
  buys nothing.
- **A false-positive count.** `^/product/[^/?]+` does *not* match
  `/product-category/`; the literal `/` after `product` prevents it, so the
  count of 6 is honest.

**Do not widen the regex.** For case 2 it sends fetches after listing pages
forever and recovers nothing.

One archaeological note: CC-MAIN-2020-16 holds a completely different
**pre-WooCommerce** djor.fo — 86 distinct paths, `.html` extensions,
category-first, with 7 code-shaped PDPs of the form
`/<category>/<sub>/<supplier-code>_<slug>.html`, e.g.
`/kettur/mattur/no-TX40230_matta-til-kettuvesi-mimi-38-38-cm.html`. That scheme
exists in **one crawl only** (2019-04 and 2018-34 hold zero records for the
host), so 7 PDPs in a single capture is a price point, not a series — not worth
a second regex branch. If anyone ever does chase it, note the mixed case
(`/Kettur/Kettulukur/`): `archive_path_re` runs against the raw path and is
case-sensitive.

Historical series for djor_fo must therefore come from ongoing live scraping,
not from CC.

`archive_prefix` on both sources was shortened to the bare registrable host on
2026-09-02. It is a plain **string** prefix applied to cdx lines *before*
`archive_path_re` is consulted, so a path in the prefix hard-caps what any regex
can see, and a wrong one fails silently — no manifest, no miss record, no error.
Filtering is `archive_path_re`'s job. Over-inclusion is free (`surt_prefix`
rstrips the trailing slash regardless), and a bare host survives the URL-scheme
migrations that break path prefixes.
