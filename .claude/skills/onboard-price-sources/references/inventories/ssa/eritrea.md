# Eritrea

_Inventory written: 2026-09-28_ (w40 institutional/diaspora pass — first pass
to ship anything for this country; the domestic-retail structural-absence
verdict below from 2026-09-01/09-02 is unchanged and still holds)

Before this pass: 0 manifests of any kind (confirmed by two prior passes,
2026-09-01 and 2026-09-02, both scoped to domestic online grocery/retail).
**Result: 2 shipped.** This pass deliberately searched two angles the prior
passes never covered — institutional/tariff sources and diaspora/regional
marketplaces — per the w40 brief, which named both as acceptable coverage
for a country with this little e-commerce.

## Shipped

| Source | Scaffolding | Analytical role | COICOP | Notes |
|---|---|---|---|---|
| `eritel_tariffs` | fetcher | tariff | 08.3.0 | EriTel, Eritrea's sole state-owned telecom operator (`eritel.com.er`). Mobile GSM, fixed PSTN, VDSL/ADSL/Wifi/VSAT internet tariff schedules — plain server-rendered HTML tables, no JS, no WAF (plain `requests` clears it). 189 rows verified live 2026-09-28. |
| `raenashop_er` | spider | retailer_sku | wide (cosmetics, home/kitchen incl. coffee-ceremony sets, food and herbs and drinks) | Eritrean/Ethiopian diaspora import store, Netherlands-based (`raenashop.com`). Open, unauthenticated WooCommerce Store API, 287 products across 15 pages, page-1/page-2 product-id sets confirmed disjoint. EUR pricing only (currency selector offers EUR/USD/GBP/SEK/NOK/DKK/CHF/CAD/AUD, never ERN) — this is diaspora-buyer pricing, not a domestic Eritrean price level, but it is exactly the "diaspora/regional marketplace" coverage the brief calls acceptable given the confirmed absence of domestic retail. 99 rows verified live 2026-09-28 (test cap; full catalog is 287). |

## Dead ends this pass

| Candidate | URL | Verdict | Notes |
|---|---|---|---|
| Naqfana | naqfana.com | blocked (login wall) | Markets itself as "the trusted Eritrean diaspora marketplace... send livestock, groceries, electronics and gifts." React SPA; the entire catalog sits behind account registration (phone + email + name + country, "no customer password needed") — no product is visible pre-auth, and no public catalog endpoint exists in the rendered JS bundle (`/api/*` there is auth/messaging/wishlist only). Probably the single best-matching diaspora source in scope, but not scrapeable without creating an account. |
| EriMarket | erimarket.shop | no_catalog | Next.js storefront, real WooCommerce-shaped currency selector (EUR/USD/GBP/SEK/NOK/DKK/CHF/CAD/AUD), but its entire product listing is 8 items literally named "E2E Test Shop" / "Test Shop" — seed/test data from a dev deploy, not a live catalog. Worth a recheck in 3-6 months if it goes live for real. |
| NatnaShop | natnashop.com | out_of_scope | Shopify, open `/products.json`, EUR pricing. Catalog is print-on-demand identity merch (Eritrean-flag t-shirts, hoodies, jerseys, graduation stoles, sneakers) — not staple consumer goods for a PPP basket, same trap class as the ISO-documents WooCommerce store flagged in `classification.md`. |
| Habesha Outlets | habeshaoutlets.com | out_of_scope | Shopify apparel dropship store, narrow (single "Habesha Dress" product line), titles heavily SEO-stuffed ("Ethiopian Shop Near Me"), Ethiopia-branded throughout — not meaningfully Eritrea-specific. |
| Grmawit | grmawit.com | out_of_scope | Shopify apparel dropship store, "Europe's largest Ethiopian and Eritrean products retailer" by self-description, but the sampled catalog is exclusively "Ethiopian Traditional Dress" SKUs, some literally suffixed `(Copy)` — duplicate/placeholder-shaped listings, Ethiopia-branded. |
| Massawa Port Authority | massawaporteritrea.com | no_catalog | Live site (Elementor/WordPress), reachable, but its tariff line item reads verbatim "Competitive Port Tariff : Available on request" — no published schedule exists to source. |
| University tuition (7 public colleges) | — | out_of_scope | Multiple independent sources agree Eritrean public higher education is free (state-funded, no verified private alternative) — there is no fee schedule to source, not a search gap. |
| Himbol Financial Services | erihimbol.com | not probed | Government-linked remittance/FX service publishing real-time exchange rates. Out of scope for a goods/services PPP price basket (FX reference, not a priced catalog) — not chased further, flagged only in case a future FX/aggregate_proxy pass wants it. |
| Water corporation, agricultural marketing board, hospital charges, Ministry of Trade price list | — | not found | English-only `ddgs` sweep (37 queries total, backends pinned) returned nothing Eritrea-specific for any of these four verticals — hits were false positives for other countries (a Botswana water utility, a California hospital chargemaster) or generic global import-tariff aggregators (not retail/consumer prices). |

## Gap: local-language search not run, and countries.yaml is missing Tigrinya

This pass ran English-only `ddgs` queries. `src/configs/countries.yaml` lists
Eritrea's `languages:` as `[en, arabic]` — **Tigrinya is missing**, despite
being the language the one real consumer-facing find (Naqfana) actually ships
in (`<html lang="ti-ER">`, Tigrinya-first copy). A Tigrinya-language sweep for
NSO/utility/agricultural-board material was not run this pass and is the most
likely place to find something this pass missed — flag `countries.yaml` for a
`languages:` fix (add `ti`) before the next Eritrea pass.

## Verdict

**Domestic online retail:** still a confirmed structural absence — two
independent prior passes (2026-09-01, 2026-09-02) found none, and nothing in
this pass contradicts that.

**Institutional tariffs and diaspora marketplaces are NOT structurally
absent.** This pass shipped one real example of each in under two hours of
English-only search. The right framing for Eritrea going forward is "no
*domestic* e-commerce," not "no e-commerce" — a future pass should keep
working the institutional-vertical and diaspora-marketplace angles (ideally
adding a Tigrinya sweep) rather than re-confirming the retail absence a third
time.

## Next steps

- Fix `countries.yaml` to add `ti` (Tigrinya) to Eritrea's `languages:`.
- A Tigrinya-language institutional sweep (NSO, agricultural marketing board,
  water/electricity utility) — the English sweep this pass ran came back
  empty on all four verticals it tried.
- Naqfana (naqfana.com) is worth a second look if a future pass is willing to
  register a throwaway account to see past the login wall — it is the
  closest-matching "send goods to Eritrea" marketplace found and was not
  ruled out on data quality, only on access.
- Do not re-chase domestic online grocery/retail; three independent passes
  now agree it does not exist.

---

_Inventory written: 2026-09-02_ (search-starved re-run; supersedes the
2026-09-01 pass)

Before this pass: 0 manifests of any kind. **Result: 0 shipped — and the one
open thread the previous pass left is now CLOSED.**

## The Asbeza thread is closed: it is Ethiopian, not Eritrean

The 2026-09-01 file's single live lead was the "Asbeza" grocery-delivery app
(`com.ecwid.ShopAt.Asbeza`), whose guessed `asbeza.com` served a parking page.
It asked for "one more WebSearch-budget pass specifically to find its real
domain before writing this off".

That search was run. The real domain is **`asbeza.net`, and Asbeza operates in
Addis Ababa, Ethiopia — not Asmara, Eritrea.** Its own about page describes it
as "Ethiopia's first grocery delivery service", delivering from stores in
Addis. The previous inventory had attributed an Ethiopian company to Eritrea.
There is no Eritrean Asbeza to find.

**Do not re-chase this lead.**

## Bonus lead for another country

`asbeza.net` (Ecwid-hosted) and `mohasbeza.com` are both live Ethiopian
grocery storefronts. Ethiopia currently sits at 5 sources / 2 food and is on
the Tier C list of the search-starved plan — these two are free candidates for
whoever runs Ethiopia next. Recorded here because this is where they were
found; they belong in `ssa/ethiopia.md` when that pass happens.

## Verdict: structural absence, now with evidence

No delivery marketplace (Jumia / Glovo / Bolt / Yango) lists Eritrea, and no
independent e-commerce domain was found for the physical Asmara grocers
(Day-To-Day Discount, Family Supermarket) that directory sites list. Combined
with Eritrea's single state-run ISP and very low internet penetration, this is
a genuine structural absence rather than a search gap — and unlike the
2026-09-01 pass, that conclusion no longer rests on an unresolved lead.

## Next steps

- None. Do not spend further discovery budget on Eritrean online retail; it
  does not exist. Revisit only if the telecom sector liberalises.
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

---

## UPDATE 2026-09-01 (second pass) — Asbeza lead CLOSED. It is ETHIOPIAN, not Eritrean.

The pass above left the Asbeza app (`com.ecwid.ShopAt.Asbeza`) as "an open thread
— worth one more WebSearch-budget pass specifically to find its real domain". That
search was run, and it resolves the thread in the negative:

**Asbeza is an Addis Ababa (Ethiopia) grocery-delivery service, not an Eritrean
one.** Its real domains are `asbeza.net` and `asbeza.et` — both live (HTTP 200,
~78 KB, Ecwid fingerprint confirmed via `curl_cffi impersonate=chrome124`), both
describing "Ethiopia's first online grocery delivery service ... in Addis Ababa",
with a Facebook page located in Addis Ababa. The earlier pass inferred Eritrea
from the app name; *asbeza* (አስቤዛ) is simply the Amharic word for groceries, and
Amharic is an Ethiopian language. The parked `asbeza.com` it probed was a
red herring unrelated to either country.

With the only open thread closed, the pass above's structural read is now the
settled verdict: **Eritrea has no online retail sector** (single state-run ISP,
minimal internet penetration, no pan-African delivery marketplace lists the
country). Treat as a **structural absence**, not a search gap. Do not re-sweep
Eritrea for grocery e-commerce.

Spillover lead for another country: `asbeza.net` is a live, unblocked Ecwid
storefront and Ecwid exposes a documented open storefront API. Ethiopia already
clears the coverage bar (5 manifests), so this is low priority — but it is a
free, verified candidate if Ethiopian food depth is ever wanted.
