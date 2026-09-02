# Liechtenstein — price source inventory (eca/western_europe/liechtenstein)

_Inventory written: 2026-09-01_ (wave 13)

Wave-13 brief: started at 2 sources / 0 food (`eurostat_electricity`,
`eurostat_gas`, both shared Eurostat tariff fetchers). Target >=5 sources
AND >=2 food-and-beverage sources. Only one candidate was supplied
(`outputs/sources_pending_will.xlsx`, "Coop / Migros (via CH)", coop.ch,
SUSPECT, GOTCHA "Do not double-count with Switzerland"); `sources_pending_jero.xlsx`
had no Liechtenstein row. The brief explicitly directed: build the four
named domestic candidates first (LKW, LGV, Telecom Liechtenstein/FL1, Amt
für Statistik), then spend what's left on the Swiss-locality food question.
**Result: 7 sources / 2 food, target cleared on both counts.**

## Domestic non-food sources built (4, none touching the locality question)

| Source key | What | Rows verified 2026-09-01 |
|---|---|---|
| `lkw_stromtarife` | LKW (Liechtensteinische Kraftwerke) — the country's own electricity utility, LKWclassic fixed-price tariff, two dated periods x 3 bands x 3 product tiers | 15 rows, 0 dup hash |
| `waerme_li_erdgas` | Liechtenstein Waerme (rebrand of LGV) — Festpreis (annual) + Floatpreis (rolling monthly) gas tariffs, discovered off `/downloads` | 7 rows, 0 dup hash |
| `fl1_mobile_li` | FL1 — Telecom Liechtenstein AG's consumer mobile-plan storefront (telecom.li itself now redirects to a wholesale-only portal; one company, not two) | 20 rows, 0 dup hash |
| `ospelt_li` | (counts as food, see below) | — |
| `hofkellerei_li` | (counts as food, see below) | — |

`eurostat_electricity`/`eurostat_gas` were left untouched (already counted,
brief said don't rebuild).

## Amt für Statistik Liechtenstein — DEAD, not a depth/gold problem

Searched (`site:llv.li Konsumentenpreisindex`) and found the actual
publication: `www.llv.li/de/news/landesindex-der-konsumentenpreise-im-*`,
a monthly LIK (Landesindex der Konsumentenpreise) news release, base
"Dezember 2025 = 100" per the search snippet, with wording suggesting the
office "monthly adopts" the Swiss national CPI rather than compiling an
independent LI-weighted basket (unconfirmed — see below, could not reach
the page to check). **Whole `llv.li` zone (including the `as.llv.li`
statistics-office subdomain) is behind a genuine Cloudflare Turnstile
interactive challenge** — `cf-mitigated: challenge`, confirmed failing
both `curl_cffi` (chrome124/chrome120/safari17_0) and headless Playwright
per the mandatory two-lever gate. See `known_blockers.md` → "Cloudflare
interactive challenge" for the full entry. This closes out the
`cpi_benchmark` candidate for this wave — genuinely blocked, not a search
miss. **Open question for a future wave (needs the WAF cracked first):**
is Liechtenstein's LIK an independently-weighted series or a straight
republication of the Swiss LIK under a different name? The brief flagged
this distinction as analytically important and it remains unresolved.

## The Swiss-chain locality question — reasoning and result

Read `denner_ch.yaml` (Migros-owned, wine-only Nuxt SSR shop, channel
specialty-food, coicop 02.1.1) and `koro_ch.yaml`/`nu3_ch.yaml` before
building anything, per the brief.

**Coop and Migros/LeShop — the two obvious candidates — are both
technically dead**, confirmed against the mandatory two-lever gate:

- **coop.ch** — DataDome bot-protection, `x-datadome: protected`, HTTP 403
  on curl_cffi (all 3 profiles) AND headless Playwright (same
  `geo.captcha-delivery.com` challenge stub after an 8s wait). Genuine
  block. See `known_blockers.md` → "DataDome bot-protection".
- **migros.ch / leshop.ch** (Migros' e-grocery arm — "Commandez en ligne...
  nous vous livrons vos courses à votre porte") — plain `requests` gets a
  flat 403; curl_cffi impersonation AND Playwright both "succeed" at
  HTTP 200 but serve an IDENTICAL 213,649-byte `<title>maintenance</title>`
  page on every path on both domains — a content-level soft-block, not a
  real outage (same page, byte-for-byte, on two domains at two different
  times). Treated as a genuine block per the gate's spirit. See
  `known_blockers.md` → "SSL certificate mismatch" section (grouped there
  as the nearest "retired/soft-blocked domain" heading) — actually filed
  under its own note beside the DataDome entry.
- **Denner's own grocery assortment** is already documented (in the
  existing `denner_ch.yaml`) as physical-store-only; only its wine shop
  sells online, and that source already exists — building a second
  Liechtenstein-scoped manifest against the exact same wine shop would be
  the wave-9 Puerto-Rico "same shelf" defect by construction (100%
  overlap is guaranteed, not just likely), so this was not attempted.
- **Spar** — spar.ch is a brochure/investor corporate site with a
  store-locator, no online shop link anywhere; `spar.li` does not resolve.
  No Spar e-commerce reaches Liechtenstein. Dead end, recorded in
  `known_blockers.md`.
- **Hofladen Express** (hofladen-express.ch) — a farm-shop delivery
  service genuinely based partly in Bendern, LI (found via WebSearch,
  explicitly served "Liechtenstein, Ostschweiz und die Stadt Zürich") —
  would have been an excellent, unambiguous domestic candidate, but the
  domain has been squatted: every path now serves a "Dragonia Casino
  Online" gambling-affiliate page. Genuinely dead (rule 13: expired
  domain + injected spam), not a WAF. A multi-vendor marketplace
  (`laedelishop.ch`, Zurich-operated, WooCommerce, has an "Essen &
  Trinken" category) may still carry a Hofladen Express listing, but its
  own Liechtenstein-delivery scope could not be verified in the time
  budgeted this wave and it was not built.

**Given all of that, the honest answer for the Swiss-chain question
specifically is: no Swiss chain was built for Liechtenstein this wave.**
Both obvious candidates are dead, Denner would collide with the existing
Swiss manifest by construction, and Spar/Hofladen Express have no reachable
storefront. The brief's own framing — "the honest answer may be that
Liechtenstein cannot have independent food sources at all" — did not end
up being necessary, though, because two GENUINELY DOMESTIC (non-Swiss)
Liechtenstein food retailers surfaced instead:

## Food sources built (2, both genuinely domestic — the locality question
## does not apply to either)

| Source key | Company | HQ evidence | Rows | Food share |
|---|---|---|---|---|
| `ospelt_li` | Herbert Ospelt Anstalt (Malbuner brand) — meat/deli specialties | schema.org PostalAddress JSON-LD: Schaanerstrasse 79, Bendern, `addressCountry: "LI"`, postalCode 9487 | 223 (after excluding a "Box Builder" gift-basket configurator that inflated the raw count to 367 with synthetic combinatorial rows) | 86.1% (192/223 in a food-named product_type) |
| `hofkellerei_li` | Hofkellerei des Fürsten von Liechtenstein — the Princely House's own winery | Sells a "Pinot Noir AOC Vaduz" bottle; page states free shipping "innerhalb der Schweiz und Liechtenstein" | 29 (whole catalog — page's own loadmore counter confirms `total:29`) | 89.7% (26/29; 3 non-food gift items) |

Both were found via one targeted WebSearch each (`Liechtenstein Lebensmittel
online shop`, then following the Ospelt lead from Ospelt's own corporate
site's shop link) — not from the workbook, which had no domestic food
candidates at all.

**Product_id overlap check (rule 19), FULL sets not sampled**, against the
existing Swiss specialty-food manifests:

| Pair | Overlap |
|---|---|
| ospelt_li (352 distinct ids across all runs) vs denner_ch (573 ids) | 0 |
| ospelt_li vs koro_ch (988 ids) | 0 |
| ospelt_li vs nu3_ch (2,169 ids) | 0 |
| hofkellerei_li (29 distinct ids) vs denner_ch | 0 |
| hofkellerei_li vs koro_ch | 0 |
| hofkellerei_li vs nu3_ch | 0 |

Zero overlap in all six pairs — different companies, different platforms
(Ospelt on Shopify, Hofkellerei on a bespoke "XSite" CMS, vs Denner's Nuxt
SSR / KoRo's Shopware / nu3's Shopify-Germany), different SKU/id
namespaces. Not the same shelf.

## Final tally

7 sources / 2 food (excludes `active: false` and `aggregate_proxy`; none
of Liechtenstein's sources are either). `.venv/bin/po prices collect
--list` exits 0.
