# Cameroon — price source inventory

_Inventory written: 2026-09-01_

Wave 13 pass (the "small/hard tail" wave — thin candidate lists everywhere).
Entered the skill at Phase 3 with the brief's 2 candidates (Express Market CM,
QuickGo 237), fell through to Phase 2 discovery for the food gap once QuickGo
237 turned out to be a demo build, then filled the remaining non-food slot
with INS Cameroun's own monthly CPI note. Checked both
`outputs/sources_pending_will.xlsx` (2 Cameroon rows — the same 2 brief
candidates, nothing new) and `outputs/sources_pending_jero.xlsx` (0 Cameroon
rows). Already-covered before this pass: `yorix_cm` (marketplace,
non-food), `wfp_prices` (official_avg) — **2 sources / 0 food**. This pass
adds 3 sources, 2 of them food, ending at **5 sources / 2 food** — the bar
is met exactly, not padded past it.

## Brief-supplied candidates

| Candidate | URL given | What's actually there | Verdict |
|---|---|---|---|
| Express Market CM | https://expressmarketcm.com/ | Real Cameroonian multi-vendor marketplace (React front end over a public PocketBase backend at `/hcgi/platform/api/`), 195 vendors / 203 products spanning many verticals. Front page/API sits behind a bot-management challenge that beats `curl_cffi` impersonation (`chrome124`/`chrome120`/`safari17_0` all 403, `server: hcdn`) but is a genuine Chromium TLS/HTTP2 fingerprint check, not a cookie gate — a real Playwright page navigating DIRECTLY to the API URL, no warm-up, no cookies, gets 200 every time. Scoped (not the full blended marketplace) to its 2 genuine food-and-beverage vendor groups per rule 14. | **ACCEPT (scoped) — built as 2 sources** |
| QuickGo 237 | https://www.quickgo237.com/ | Real Next.js app, no WAF, but the entire "national marketplace" is 11 products across 6 boutiques (one shop, "Super U Express", 404s on click: "Cette boutique n'existe pas ou n'est plus disponible"). Classic demo/seed build, not the live multi-city app the workbook claimed. See `known_blockers.md` § Placeholder / seed demo-data catalog. | **DEAD — demo build** |

## What was built

- **`express_market_supermarket_cm`** (channel=supermarket, retailer_sku) — Express Market's one genuine supermarket vendor, "Yatch Center" (Bafoussam). 26 SKUs, all XAF, 0 zero/negative price, 0 blank name, 0 duplicate product_id.
- **`express_market_bakery_cm`** (channel=convenience, retailer_sku) — Express Market's 6 vendors named "Boulangerie ..." (bakeries; the source's own vendor `type` field mislabels them "Supermarche", not trusted — grouped by vendor name instead). 46 SKUs (bread/pastry plus a general grocery shelf), all XAF, clean on every check.
- **`ins_cameroun_cpi`** (channel=null, cpi_benchmark, publisher_labeled) — INS Cameroun's monthly "Note mensuelle sur l'evolution des prix" PDF, own domain, no WAF. One PDF backfills a rolling 12-month x 12-COICOP-division grid (144 rows first run), same design as the existing Sierra Leone `statssl_cpi` fetcher.

Full build rationale, measured numbers, and cold re-fetch verification are in
each YAML's `notes:` field and in the wave-13 chat report — not duplicated
here.

## Discovery pass (Phase 2) — for the food gap, once QuickGo 237 died

Per the brief: discover in French, Douala and Yaounde separately, look for
Santa Lucia / Mahima / Dovv / Casino Cameroun, check Jumia Cameroon.

- **Jumia Cameroon** — brief claimed "Jumia DOES operate in Cameroon, unlike
  Sierra Leone." **Not current.** Jumia suspended its main Cameroon
  marketplace in Nov 2019, keeping only a classifieds-style portal running
  afterward (per Investir au Cameroun reporting). The live `jumia.cm` domain
  today 403s with a Cloudflare Turnstile challenge AND fails TLS validation
  (`net::ERR_CERT_COMMON_NAME_INVALID`) — reads as a stale/minimally
  maintained tenant, not an active grocery storefront. See
  `known_blockers.md`. **DEAD.**
- **"Santa Lucia" name collision** — `www.santalucia.cm` resolves and loads
  (200) but is **Hotel Santa Lucia**, a hotel-booking site, unrelated to the
  real "Complexe Santa Lucia" supermarket chain (13 branches across
  Douala/Yaounde per search results — goafricaonline/maligah/ayilaa
  directory listings confirm the chain is real but phone/address only, no
  own website found).
- **"Casino Cameroun" name collision** — `casinocameroun.com` resolves and
  loads (200) but is a **gambling/betting-affiliate review site**
  ("Casinos en ligne au Cameroun", licensed operators list, MoMo/OM payment
  info for online betting) — nothing to do with the Casino supermarket
  group. No genuine Casino-brand Cameroon storefront domain found this pass.
- **Santa Lucia via Familov** — found via search: `familov.com` is a
  diaspora grocery-delivery platform that lists real Cameroonian supermarket
  branches (confirmed: "Au Supermarché SANTA LUCIA BONABERI / DLA", real
  product names — Alveole 30 Oeufs frais, SUCRE SOSUCAM MORCEAU 1KG, Huile
  raffinée OLEO 5L, etc.). **Rejected for locality/currency (rule 8):** the
  site's ONLY currency options are EUR/USD/CAD/GBP (confirmed via its
  `currency-change/<CCY>` links) — there is no XAF display mode at all. This
  is a remittance-style service priced for a diaspora buyer abroad, not the
  local Cameroon shelf price a PPP comparison needs. Not built.
- **Mahima, Dovv** — no reachable, live e-commerce domain found for either
  chain this pass (a `dovv.cm` resolves but serves a self-signed cert with
  no clear storefront; `www.dovv.com` 404s). Not pursued further given the
  gap was already closed by Express Market's supermarket/bakery split.
- **MINCOMMERCE fuel prices** (brief's top non-food suggestion) — turned out
  to be a misattribution: fuel pricing in Cameroon is regulated by **CSPH**
  (Caisse de Stabilisation des Prix des Hydrocarbures, `csph.cm`), not
  MINCOMMERCE directly. CSPH's own `pricestructure.php` 500s and its only
  linked price-structure PDF is stale (Nov 2021) — see `known_blockers.md`.
  Not built this pass; INS Cameroun's CPI note was cheaper and already
  includes fuel-import-cost figures as a byproduct (Encadré 1).
- **Knoema/OpenDataForAfrica CPI portal** (`cameroon.opendataforafrica.org`,
  linked from the INS homepage) — genuine Cloudflare Turnstile interactive
  challenge, not a TLS-fingerprint issue. Abandoned in favour of
  `ins-cameroun.cm`'s own domain, which publishes the same CPI series as an
  unprotected monthly PDF. See `known_blockers.md`.
- **MTN Cameroon / Orange Cameroun prepaid bundles** — both domains reachable
  with no WAF, but bundle pricing renders client-side (Orange's voice/SMS
  catalogue page is a near-empty megamenu shell in raw HTML); not sniffed
  this pass since the 3-source bar was already met via `ins_cameroun_cpi`.
  Recorded in `known_blockers.md` as a real next-pass lead, not a dead end.

## Conclusion for this pass

Cameroon ends this pass at **5 sources / 2 food** — bar met exactly.
Locality confirmed for all 3 new sources (Express Market's two vendor groups
are Bafoussam-based Cameroonian merchants pricing in XAF; INS Cameroun is the
national statistics office). No same-shelf overlap with `yorix_cm` (different
company/backend — Supabase vs PocketBase) or `wfp_prices` (WFP official
average, different methodology). If a future pass wants margin above the
bar, the two next-cheapest untried leads are Orange/MTN prepaid tariffs
(client-side rendered, needs a Playwright network capture) and re-checking
Mahima/Dovv for a live storefront.
