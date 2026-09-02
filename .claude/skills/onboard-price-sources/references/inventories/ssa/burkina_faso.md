# Burkina Faso — price source inventory

_Inventory written: 2026-09-01_

Cold-start pass (wave 9). Country had **zero** country-specific sources before
this run — only `wfp_prices` (shared regional fetcher). Ended at **7 sources
/ 2 food** (target was >=5 / >=2). Search was conducted in FRENCH throughout,
per the wave-9 brief's explicit warning that an English "supermarket Burkina
Faso" search is the lowest-yield move available.

## Wins (onboarded this pass)

| Source | analytical_role | channel | Notes |
|---|---|---|---|
| `insd_ihpc_cpi` | cpi_benchmark | null | INSD monthly IHPC (Base 2023) national NCOA-IHPC group index table. 250 rows/50 groups on first pull. |
| `insd_avg_prices` | official_avg | null | Same INSD monthly workbook, "Tableau 4" regional average prices — 31 products x 13 regions, 403 rows. Mostly food but bundles fuel/wood/charcoal too (wide, not narrow). |
| `onea_water_tariff` | tariff | null | ONEA household water/sanitation tariff PDF (only current schedule live, no archive). 10 rows. |
| `orange_mobile_tariff` | tariff | null | Orange Burkina's ARCEP-mandated commercial-offers PDF catalog, 35 pages, genuinely tabular. 126 rows after fixing two coordinator-flagged defects (positional-suffix identity collisions and a short-code-as-price bug in premium SMS/VAS rows) -- see the YAML notes for detail. |
| `hyanta_bf` | retailer_sku | **fresh-market** | Ouagadougou fresh-market grocery delivery, small static PHP site (~65 products). 100% food. |
| `centralboucherie_bf` | retailer_sku | **specialty-food** | Ouagadougou butcher/fine-grocery ("CentralBusiness"), custom-built single-page catalog (48 rows after dropping 3 out-of-stock cards). 100% food. |

## Dead ends (recorded so the next run doesn't repeat them)

- **SONABEL (electricity tariff)** — `sonabel.bf` and `www.sonabel.bf` both
  resolve via DNS (8.8.8.8 and 1.1.1.1 agree: 102.211.121.6) but the TCP
  connection itself times out on both HTTP and HTTPS, on every retry. Not a
  DNS lie — genuine connectivity gap, consistent with the brief's warning
  about limited connectivity to some BF government/utility sites. No
  archive.org fallback attempted this pass (budget). **Revisit**: retry
  live, or try Wayback Machine for a historical tariff snapshot.
- **ARCEP BF "Encadrement des tarifs"** page (`www.arcep.bf/encadrement-des-tarifs-2/`)
  — live and reachable, but is a policy/methodology page about the *postal*
  universal-service tariff-capping framework, not a live tariff table with
  numbers. No price data to extract. Not pursued as a source.
- **`gobusiness.bf`** (business directory, had a "supermarchés" category
  listing) — domain does not resolve at all via 8.8.8.8 or 1.1.1.1 (genuinely
  dead, not a sandbox DNS lie).
- **`mapsme.fr`** (supermarket directory claiming "adresses, numéros de
  téléphone... sites web") — Cloudflare 403 on `curl_cffi` across
  chrome124/chrome120/safari17_0 (mandatory-gate confirmed genuine block).
  Even if unblocked it is a directory, not a source, and would only have
  been useful to find retailer websites — the directory itself is not
  needed since the retailers found (Marina Market, Scimas, Supermarché
  Caravelle) all turned out to have no website anyway (see below).
- **`www.ouagadougou.online`** (marketplace/courier directory) — resolves
  fine (72.60.81.226 on both resolvers) but the connection genuinely times
  out on both `curl_cffi` and plain `curl`, retried once per the brief's
  rule. Not a DNS lie, a live-but-unreachable host.
- **`apexb.bf`** (had a `/catalogue-de-produits/fruits-et-legumes` URL
  surfaced by search) — resolves (51.83.107.56) but connection times out on
  both `www.apexb.bf` and bare `apexb.bf`, retried once. Unreachable.
- **`fasoranana.com`** (Poste Burkina Faso's own e-commerce marketplace,
  with a "Supermarché" category tree: Produits alimentaires/Boissons/
  Produits frais/Épicerie/Produits de nettoyage) — site is live and fully
  functional (Light/Dark mode, cart, full category nav) but **every single
  category returns "0 article(s) trouvé(s)"** — the platform has launched
  with zero listed products from zero active sellers. Structural absence,
  not a scraping problem. **Revisit in a future wave** — if Poste BF
  onboards real sellers this becomes a genuine marketplace-directory lead
  (would need "onboard first-party merchants" treatment per the skill's
  marketplace pattern, not the aggregate catalog itself).
- **`cesmonjour.com`** (Ouagadougou meal/grocery delivery app, explicitly
  advertises "restaurants, patisseries et supermarchés" and even carries an
  SEO landing page at `/marina-market-ouaga`) — confirmed **app-only, no web
  catalogue**: every route on the domain (including the Marina-Market-named
  page) renders the exact same static marketing copy; no product listing,
  no prices, no functional ordering UI in the HTML/JS actually served. JS
  bundle chunks grepped for an `apiUrl` literal — none found (property
  accesses only, real config not present in the fetched chunks). Real
  value here was confirming Marina Market IS a genuine merchant in
  Ouagadougou (see below) — just not reachable through this route.
- **Marina Market** (Burkina Faso's largest supermarket chain, ~5 branches
  in Ouagadougou + 1 in Bobo-Dioulasso, IFC-backed) — **no official website
  found**. Only presence is Facebook (`facebook.com/MarinaMarketofficielle/`)
  and directory listings (nexpages, nexpages/petitfute, gobusiness — none of
  which link out to a working retailer-owned domain). Confirmed a genuine
  "no online catalogue" case, not a search miss — multiple query variants
  tried.
- **"Surface Bleue"** (named in the wave-9 brief as a candidate) — **does
  not appear to exist under this name**. No search hit for this exact
  string in Burkina Faso; possibly a mis-transcription of another chain
  (candidates that DID surface: SCIMAS, Supermarché Caravelle, La
  Superette, Sonacof — see below). Do not re-search this exact string; if
  revisited, ask whether the intended name was something else.
- **Citec** (named in the wave-9 brief) — `citec.bf` resolves and returns
  HTTP 200, but serves the literal default nginx/Plesk placeholder page
  ("Ça marche! / It works!") — a parked or never-launched domain, not a
  retailer. No other "Citec" supermarket found in Burkina Faso searches
  (Citec is better known as a Congo-Brazzaville edible-oils manufacturer —
  likely a cross-country brief mix-up, not a real Ouagadougou retailer).
- **SCIMAS Supermarché**, **Supermarché Caravelle**, **La Superette**, **Le
  Bon Samaritain**, **Mini Alimentation Wend Song Meteba**, **Natifa
  Market**, **Sanga Market**, **Sgcofa**, **Shopette Sarl**, **Shopping
  Burkina**, **Simex**, **Socosef Burkina Faso**, **Sonacof** — all listed
  with phone numbers in the Nexpages Burkina Faso "Commerce détail et
  distribution" directory (`nexpages.com/burkina-faso/commerce-detail-distribution`),
  none have a linked website in that directory (only phone/address). A
  targeted follow-up search on SCIMAS and Caravelle independently confirmed
  Facebook-only presence, no dedicated site. **Pattern, not a coincidence**:
  Ouagadougou's brick-and-mortar supermarket sector appears to have
  essentially zero e-commerce presence as of 2026-09 — this is the honest
  finding behind the low food-source hit rate the brief warned about.
- **Jumia Burkina Faso** (`www.jumia.bf`) — confirmed live storefront exists
  (redirects, resolves), but returns HTTP 403 with the same
  `<title>Just a moment...</title>` Cloudflare-challenge signature already
  recorded for `jumia.ma` and `jumia.com.gh` in `known_blockers.md`, on all
  three `curl_cffi` TLS profiles (chrome124/chrome120/safari17_0) —
  mandatory-gate confirmed genuine block, one shared Cloudflare tenant
  across (at least) Morocco/Ghana/Burkina Faso storefronts. Not worth
  re-probing per-country; a dedicated Jumia-Cloudflare effort would need to
  crack one storefront to unlock the rest.
- **Rodwoko.com** ("Grand marché du Burkina Faso") — a genuine nationwide
  classifieds marketplace (Ouagadougou + ~20 other towns) with an
  "Alimentations & Supermarchés" category, but on inspection that category
  is populated by individual private-seller classified ads (subscriptions,
  board games, phone SIMs mixed in under "food"), not real supermarket
  digital shelves — correctly a `channel: marketplace` candidate, which
  does NOT count toward the food target even if onboarded. Not built this
  pass (would have required disambiguating a genuinely mixed-quality
  classifieds catalog for a source that can't move the food count) — a
  candidate for a future non-food coverage pass if more `marketplace`-role
  sources are wanted for COICOP breadth.

## Notes for the next run

- SONABEL and `ouagadougou.online`/`apexb.bf` are TCP-timeout dead, not
  DNS-lied dead — re-resolving against 8.8.8.8/1.1.1.1 did not change the
  verdict for any of them (all agreed on resolvable addresses). Retry
  periodically; Burkina Faso connectivity is explicitly flagged as uneven
  in the wave-9 brief.
- If a future ARCEP-regulated Moov Africa Burkina catalog PDF surfaces
  (parallel to `orange_mobile_tariff`), the same auto-detecting
  table-column heuristic in `orange_mobile_tariff.py` should transfer with
  minimal changes — worth checking `moov-africa.bf` for an equivalent
  "canevas" PDF before writing a new parser from scratch.
- `fasoranana.com` is worth a periodic re-check (empty today, 2026-09-01) —
  it is a Poste Burkina Faso national marketplace platform, which if it
  gains sellers would be a strong marketplace-directory lead per the
  skill's "onboard first-party merchants" pattern.
