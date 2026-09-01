# Gabon — price source inventory

_Inventory written: 2026-09-01_

Wave 11 pass, working from pre-scouted candidates (`outputs/sources_pending_jero.xlsx`,
`Pending sources` sheet — `outputs/sources_pending_will.xlsx` has zero Gabon rows).
Entered the skill at Phase 3 with the 5 candidates the brief supplied, then fell through
to Phase 2 discovery once every one of those 5 turned out dead. Already-covered before
this pass: `cerise_ga` (supermarket), `shopenlignegabon_ga` (dept-store), `geogabon_ga`
(electronics), `pharmacie_saintemarie_ga` (pharmacy), `seeg_electricity_tariff_ga`
(tariff) — **5 sources / 1 food**. Target was >=5 sources (already met) AND >=2 food
(not met). This pass needed exactly 1 more food-and-beverage source and **did not find
one that verifies live**. Ends the pass unchanged at 5 sources / 1 food. Recording every
dead end below so the next pass does not repeat this search.

## The 5 brief-supplied candidates — all DEAD

| Candidate | URL given | What's actually there | Verdict |
|---|---|---|---|
| Ceca Gadis | https://cecagadis.ga/ | `cecagadis.ga` is NXDOMAIN on 8.8.8.8/1.1.1.1 (confirmed with authoritative DoH, not just local resolver — rule 15 checked). The live domain is **`cecagadis.com`** (200, WordPress/Elementor, `fr-FR`). `/wp-json/` has no `wc/` route — **not WooCommerce**, contrary to the workbook's platform tag. It is a pure corporate/holding-company site for the CECA-GADIS retail group (brands: Cecado, CK2, GaboPrix, Géant CK'DO, Intergros, Matelec, Maxi CK'DO, Maxigros, Sogame Equip, Super CK'DO, Supergros). Checked 4 of the brand "enseigne" sub-pages directly — every external link on every one is Facebook/Instagram/LinkedIn, zero e-commerce. | **DEAD — corporate site, no catalogue** |
| Chap Chap Gabon | https://chapchapgabon.com/ | Resolves and loads (200, custom single-page site, "12 villes" multi-vertical delivery: restaurants, épiceries, pharmacie, colis). Grepped the full HTML for `FCFA`, `produit`, `panier`, `catalogue` — all effectively empty of real product/price content; the only external links on the page are anchors (`#categories`, `#how`, …) plus one Google Fonts link and an **App Store** badge. It's a marketing landing page for a mobile app with no web ordering surface at all. | **DEAD — app-only, no web catalogue** |
| Malumbi | https://malumbi.com/ | `malumbi.com` returns NXDOMAIN from both `dns.google` and `cloudflare-dns.com` DoH (authoritative `.com` TLD servers answer directly, not a resolver cache) — the domain is unregistered/lapsed as of 2026-09-01. Search-engine cache still surfaces old page titles (`https://malumbi.com/17-epicerie`, `/15-conserves`) confirming it *was* a real PrestaShop-style grocery site (épicerie, conserves, Airtel Money) — but it is not reachable today. Tried `.shop/.africa/.ga/.io/.store` and a `shop.` subdomain variant; none resolve either. | **DEAD — domain lapsed** |
| Libre-Go Livraison | https://www.libregolivraisons.ga/ | Resolves and loads (200). It's a **courier/delivery-fee** site (motorcycle icon, "Livrer, c'est tenir parole"), not a retailer: the only `FCFA` mentions are a live delivery-fee calculator (`tarif-calcule`), a late-delivery compensation clause, and an invoice total — no `produit`, no `catalogue`, no `boutique` anywhere in the page. Matches the workbook's own note ("catalogue sits behind login") — there is no product catalogue to log into. | **DEAD — courier service, not a food retailer** |
| SendMonTchop | https://sendmontchop.com/ | `sendmontchop.com` and `www.sendmontchop.com` both resolve, but the page is a 114-byte redirect to `/lander`, which serves a GoDaddy/`wsimg.com` **parking-lander** shell (`window.LANDER_SYSTEM="PW"`, `ap:"parking"`). The domain has lapsed into registrar parking. | **DEAD — domain lapsed to parking page** |

## Discovery pass (Phase 2) — also exhausted

Once all 5 supplied candidates failed, ran a marketplace/directory sweep plus targeted
French-language search (6 `WebSearch` calls total, budget-conscious) rather than
inventing more domain guesses:

- **goafricaonline.com Gabon supermarket directory** (74 results) — every listing is a
  phone number + address only (CECADO, Carrefour Market/Prix Import, Casino, Géant
  Casino/Mbolo, Supergros, Royal Food Gabon, Poto-Poto Market, Supermarché SAMBA,
  Regabon, Chez Aziz.bon prix, ABS Center). **No URLs at all** — a phone directory, not
  a source generator.
- **africannuaire.com food-distribution directory** — of 15 listed businesses only 3
  gave a URL: `cecagadis.com` (see above, dead), `priximport.com`, `san-gel.com`.
  - `priximport.com` — the corporate site of **Prix Import**, the operator behind
    `cerise_ga` (per that YAML's own notes). Loads fine but is a brochure WordPress
    site with a 2019-dated blog and zero shop/boutique/catalogue content. Even if it
    had one, it would be the same operator/shelf as the existing `cerise_ga` (rule 19)
    — not pursued further either way.
  - `san-gel.com` — domain has been repurposed; now serves an unrelated Indonesian
    skincare-brand site (`MEGAVIP`), nothing to do with Gabon or food.
- **mbolo.com** (Casino Group's Gabon hypermarket brand) — resolves but is a
  domain-broker parking page (`brandsmat.com` sale widget).
- **carrefour.ga** — resolves (same IP block as `priximport.com`) but serves a static
  "Under Construction" placeholder (`Untitled Document`, `underconstruction.jpg`).
- **jumia.ga** — resolves but sits behind a Cloudflare "Just a moment…" challenge; Jumia
  does not operate a Gabon storefront (not in Jumia's current country list), so this
  reads as a squatted/unrelated domain, not a real Jumia tenant. Not pursued.
- **isaimarket.com** ("Isai Market", surfaced repeatedly in search snippets as a live
  Libreville grocery-delivery service) — NXDOMAIN confirmed via `dns.google` and
  `cloudflare-dns.com` DoH against the authoritative `.com` servers. Lapsed, same
  pattern as Malumbi.
- **systemelad.com** ("Système LAD", Libreville/Akanda/Owendo delivery) — does not
  resolve at all (no A record on 8.8.8.8).
- **gabon4you.com** — loads, but is a general "Guide du Gabon" WordPress content site,
  not a retailer.
- **yoboresto.com** — resolves (Cloudflare-fronted) but the origin is down: HTTP 522
  ("Connection timed out") on two separate retries a few seconds apart. Restaurant/
  fine-grocery delivery aggregator per its own listing copy, but currently
  unreachable.
- **Glovo / Yango / Bolt Food** — none currently operate a Gabon storefront per search
  results (Yango Delivery is Côte d'Ivoire only; Bolt Food's country list excludes
  Gabon). No marketplace-of-merchants angle available for Gabon at this time.
- **Le Boucher Libreville** (specialty butcher, South African meat import) —
  Facebook-page-only, no independent website. **Le Palais du Vin** (wine/fine grocery,
  2 physical locations) — directory-listed with phone numbers only, no website found.
  Both are real Libreville food businesses but structurally unscrapable (no web
  presence at all).
- Random plausible-name domain guesses (`shop241.com`, `241shop.com`, `gabonshop.com`,
  `myshop.ga`, `epicerie241.com`, etc.) were tried as a last resort; the ones that
  resolve are unrelated/parked, the rest don't resolve. Recorded here only so a future
  run doesn't re-try the same guesses — this was a low-yield tactic, consistent with
  the skill's own warning against generic guessing.

## Conclusion for this pass

**Gabon's online food-and-beverage retail landscape currently has exactly one live,
scrapable source: `cerise_ga`.** Every other named or discoverable candidate is either
(a) a corporate/brand site with no e-commerce, (b) an app-only delivery service with no
web catalogue, (c) a non-food courier service, or (d) a domain that has lapsed/parked —
and this last category (Malumbi, SendMonTchop, Isai Market, Système LAD all lapsed) is
common enough in this market that Gabonese food-delivery startups appear to have a short
shelf life; several distinct ones surfaced in search-engine caches as "live" services
that no longer resolve. **This pass ends at 5 sources / 1 food — an honest shortfall
against the >=2 food target.**

Worth a fresh check on a future pass (~6 months out, per the skill's staleness
convention), roughly in priority order:

1. Re-check whether Malumbi, SendMonTchop, or Isai Market have re-launched under a new
   domain — all three had real épicerie/grocery content in search-engine caches, so the
   underlying businesses may still exist even though the domains died.
2. Re-check `cecagadis.com` for an added online-ordering module — it's Gabon's largest
   retail group by far, so any future e-commerce launch there would be high-value.
3. `wfp_prices` (the shared `_shared.ssa.wfp_food_prices` regional fetcher already wired
   for 13+ SSA countries) was **not** checked for Gabon coverage this pass since, even if
   available, it would ship `channel: null` (`analytical_role: official_avg`) per
   existing-source convention and would not count toward the food-channel bar. Still
   worth adding later as a `cpi_benchmark`/`official_avg` complement if HDX carries a
   Gabon dataset — just not a fix for this pass's specific ask.
4. No fresh-market or specialty-food channel candidate was found with any live web
   presence — Le Boucher Libreville and Le Palais du Vin are the two identified
   specialty-food businesses but neither has a website today.
