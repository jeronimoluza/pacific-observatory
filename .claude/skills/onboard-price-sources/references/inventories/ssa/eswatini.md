# Eswatini

_Inventory written: 2026-09-12_ (candidate-list pass; supersedes nothing —
appends to the 2026-09-02 and 2026-09-01 sections below, which were
grocery-only sweeps and remain correct on grocery)

Worked from a supplied candidate list (21 untried PENDING rows from
`prices_sources_status.xlsx`, all tagged "NEEDS-CUSTOM-CRAWLER"), entered
at Phase 3. No discovery was run. **Result: 5 shipped, 16 rejected.**

This was a low-coverage country (3 of 257 COICOP leaves filled), so the
coverage-density rule applied: take whatever verifies, cheapest first, no
gap ranking.

## Shipped

| Source | URL | Platform | Rows (verification run) |
|---|---|---|---|
| britemanservices | britemanservices.com | React/Vite SPA, product array in `/assets/index-<hash>.js` | 16 |
| swaziswap | swaziswap.com/catalogue | Django SSR, `.product-card` | 8 |
| mitsubishieswatini | mitsubishieswatini.co.sz | WordPress + Elementor, homepage model blocks | 8 |
| eec_domestic_tariffs | eec.co.sz/domestic/tariffs/ | static HTML table (fetcher) | 6 |
| autofin_co_sz_showroom | autofin.co.sz/showroom/ | WordPress + Auto Listings plugin | 5 |

## Dead ends (measured this pass, 2026-09-12)

| Candidate | URL | Status | Notes |
|---|---|---|---|
| Shoprite Eswatini specials | specials.shoprite.co.sz | **DEAD — empty text layer on the CURRENT leaflet; RE-CHECK** | The most valuable near-miss of the pass and the one worth revisiting. The 2026-09-02 inventory correctly called www.shoprite.co.sz a brochure, but MISSED this FlippingBook leaflet subdomain. Archived leaflet `szlowpricesavings01sep14sep2025` carries a full SEO `<div id="text-container">` holding the leaflet's own text — a regex over it yields **138 clean (price, product, size) rows** across 2 pages, food-dominant (COICOP 01/02), e.g. "999 SUNNY BAKED BEANS IN TOMATO SAUCE 410g" → E9.99 (prices are cents-encoded, no decimal point). But the CURRENT leaflet, `szshopriteprice03sep17sep2026` — the only one www.shoprite.co.sz/specials.html links — ships that div containing only the title: 48 characters of text, 0 rows. No FlippingBook text/search asset is exposed either (`files/assets/common/text/page0001.js`, `files/search/search.json`, `files/assets/basic-html/page1.html` all 404), and `specials.shoprite.co.sz/` is a 62-byte stub with `/deals/` returning 403, so there is no leaflet index to walk for older editions. Re-probe the current leaflet's text-container on each pass: if the publisher re-enables text extraction this becomes Eswatini's only supermarket source and is worth ~140 food rows a fortnight. |
| MarketSquare (FNB Eswatini) — vehicles | marketsquare.co.sz/getlisted/used-cars.php | **BELOW SHIP GATE — 2 rows** | Server-rendered PHP, no WAF, clean per-listing `vehicle.php?car_id=` urls. But only two vehicles are listed (car_id 137 Jaguar F-Pace, 138 Audi SQ5) and `?page=2` returns a byte-identical page — the "Listed by Customers" section is empty. Fails the >=5-row gate. Worth re-checking: the platform is FNB-backed and the plumbing is sound, so the only thing missing is inventory. |
| MarketSquare (FNB Eswatini) — properties | marketsquare.co.sz/getlisted/properties.php | **OUT OF BASKET — for-sale only** | 10 listings with prices (property_id 36-46, E1.995m-E6.5m) and would clear the row gate, but every one is a dwelling **sale**, and dwelling purchase is capital formation, not COICOP household final consumption. No rental section exists on the site. This matches repo precedent: `ethiopiapropertycentre_et` and `propertygibraltar_com` both deliberately scope real-estate to rentals (04.1.1) and exclude for-sale. |
| Buy Eswatini | buyeswatini.shop/291/Product/All | **BELOW SHIP GATE — 4 rows** | Genuine Eswatini produce marketplace and correctly SZL-denominated (Lettuce 20.00 SZL, Spinach 25.00, Onions 50.00, Cabbages 30.00) — exactly the fresh-produce COICOP 01.1.7 leaves nothing else here reaches. The whole catalog is those 4 items; /Product/Food and /Product/Ingredients return the same 4. Highest-value re-check target after Shoprite: one more seller onboarding on their side clears the gate. |
| SLTA bus fares | eslta.org | **BELOW SHIP GATE — 3 rows** | Three hardcoded route cards in the HTML (Mbabane-Manzini E30, Mbabane-Siteki E60, Manzini-Nhlangano E65) plus a "Smart Fare Calculator" whose rate table is not in the page's JS — the calculator's 6x6 origin/destination matrix is not enumerable from the served markup. COICOP 07.3.1 would be a genuine gap fill if it ever grew. |
| TimotoTraders | timototraders.co.za | **DEAD — API is auth-walled** | React SPA whose listings render client-side ("Loading…"). Backend located: Supabase at `vrnavsacgabucmmpuymf.supabase.co`, anon key baked into `/assets/index-DM1z9gXg.js`, tables `listings` / `profiles` / `favorites`. `profiles` and `favorites` return `[]` to the anon key but `listings` returns HTTP 401 `42501 permission denied for table listings` — RLS is on and anon SELECT is not granted. Nothing to scrape without a login. |
| Quick Messànger | quickmessanger.com | **DEAD — not a catalog** | Eswatini business-directory / encrypted-messaging PWA. The 100+ currency tokens on the homepage are its own subscription payment plans, not products. `/adverts` renders 200 but is an empty JS shell with zero prices; `/shop` and `/products` 404. |
| Lesi Incorporated | lesi-inc.com | **DEAD — wrong business** | Listed as "vehicle and property listings"; it is a 3.6 KB one-page marketing-and-communications agency site with zero prices. |
| Skyfly | skyfly.mobi/store | **DEAD — empty** | Returns HTTP 200 with a 114-byte body and no title. |
| Patos | patos.co.za | **DEAD — placeholder** | `<title>patos.co.za</title>`, no prices, no catalog. Also a `.co.za` domain with no Eswatini connection evidenced. |
| Imali Smart / StorkvelKonnect | storkvelkonnect.co.za/marketplace | **UNREACHABLE — TLS handshake fails** | `curl_cffi` errors out on all three profiles (chrome124/chrome120/safari17_0) with `SSLV3_ALERT_HANDSHAKE_FAILURE`. Not a WAF — the server never completes a TLS handshake. Also a `.co.za` host. |
| Eswatini Observer classifieds | fliphtml5.com/xoczu/... | **DEAD — image-only flipbook** | A FlipHTML5 scan of a newspaper edition. Needs a full OCR pipeline over page images, and a single dated edition is not a re-collectable source. |
| newflagshop (Eswatini flags) | newflagshop.com/shop/.../eswatini/ | **OUT OF SCOPE — wrong country** | A Canadian flag retailer, `priceCurrency: CAD`, selling Eswatini-themed flags to Canadian buyers. Nothing to do with Eswatini price levels. |
| AloOui / Gigago / MollySIM / Hivoox eSIM | alooui.com, gigago.com, mollysim.com, hivoox.com | **OUT OF SCOPE — foreign vendor, USD travel pricing** | All four are global travel-eSIM vendors quoting USD (`priceCurrency: USD` on three; hivoox timed out at 35 s on every profile). They sell an Eswatini data plan to inbound travellers from abroad. That is not a price a household in Eswatini faces, so attributing it to Eswatini's price level would be wrong-country. Reject as a class, not one by one. |

Two cross-cutting notes for the next pass:

- **The `.co.za` rows in a supplied Eswatini candidate list are mostly noise.**
  Four of 21 candidates were South African domains; of those, one (timototraders)
  is genuinely Eswatini-facing but auth-walled, and three are dead or unrelated.
- **`specials.<chain>.co.sz` is a subdomain shape the grocery sweeps did not try**,
  and it is where the country's only supermarket price surface turned out to live.
  Checked this pass, though, it does not generalise inside Eswatini: DNS re-verified
  2026-09-12 confirms `pnp.co.sz`, `spar.co.sz`, `ok.co.sz`, `okfoods.co.sz`,
  `boxer.co.sz`, `picknpay.co.sz`, `friendlyfoods.co.sz` and `usave.co.sz` are all
  still NXDOMAIN, as are `specials.pnp.co.sz` and `specials.spar.co.sz`. Shoprite is
  the only SACU chain with a resolving `.co.sz` apex (`www.shoprite.co.sz`
  54.230.253.122, `specials.shoprite.co.sz` 102.217.185.58). The lesson to carry to
  OTHER countries: when a chain's apex resolves but reads as brochure-only, probe a
  `specials.` / leaflet subdomain before writing it off.

---


_Inventory written: 2026-09-02_ (search-starved re-run; supersedes the
2026-09-01 budget-limited pass)

Before this pass: `fews_net` + `wfp_prices`, 0 retail sources. **Result: 0
shipped.** An English-language search was run — the lever the previous pass
lacked — and it confirms the earlier "inconclusive-leaning-negative" read.

## What the search added

Eswatini's grocery retail is entirely South African franchise chains: SPAR,
Pick n Pay, Shoprite, Boxer, OK Foods, PnPay. Named stores confirmed in
Mbabane (OK Foods, Pick n Pay at The Mall) and Manzini (SUPERSPAR Buy N Save,
Boxer Superstores, Shoprite Busrank, Pick n Pay Family River Stone).

**No online ordering or delivery service surfaced for any of them.** The
searched result is consistent with the pattern already confirmed for Namibia
and Eswatini's other SACU/CMA neighbours: the dominant chains run brochure /
store-locator sites with no e-commerce.

## Dead ends

| Candidate | URL | Status | Notes |
|---|---|---|---|
| Shoprite Eswatini | https://www.shoprite.co.sz | **BROCHURE** | Carried forward: pan-African Shoprite Group AEM corporate template, no add-to-cart, no product markup. |
| Pick n Pay Eswatini | pnp.co.sz | **NXDOMAIN** | Probed this pass. Pick n Pay operates physical stores in Mbabane and Manzini but has no `.sz` domain. |
| SPAR Eswatini | spar.co.sz | **NXDOMAIN** | Probed this pass. The franchise's public presence is a Facebook page (`facebook.com/spareswatini`, "Buy n Save - SPAR Eswatini", Manzini). |
| OK Foods, PEP, Friendly Foods | ok.co.sz, pep.co.sz, friendlyfoods.co.sz | **NXDOMAIN** | Carried forward. |

No delivery marketplace (Jumia / Glovo / Bolt / Yango) operates in Eswatini.

## Next steps

- The realistic route into Eswatini is **not** a local domain: it is whether a
  South African parent's storefront (`pnp.co.za`, `spar.co.za`,
  `checkers.co.za` Sixty60) exposes an Eswatini delivery zone or store-scoped
  catalog. That is a South-Africa-tenant question, not an Eswatini discovery
  question, and should be answered once for the whole CMA/SACU bloc rather
  than per country.
_Inventory written: 2026-09-01_

Final F&B sweep, wave (2026-09), agent B. Cold-start (no prior inventory file
existed). Already-covered before this pass: 2 non-food sources (per the
sweep worklist), 0 food.

**Result: 0 sources shipped. No viable online grocery found.**

| Candidate | URL | Status | Notes |
|---|---|---|---|
| Shoprite Eswatini | https://www.shoprite.co.sz | **DEAD — brochure/store-locator only** | Same pan-African Shoprite Group AEM corporate template confirmed on Namibia in this same pass (generic "Home" title, "shop" text present but no add-to-cart, no product markup, no cart/checkout flow). |
| SPAR, OK Foods, PEP, Friendly Foods (Eswatini) | (no domains found) | **NOT PROBED — no resolvable domain** | `spar.co.sz`, `ok.co.sz`, `pep.co.sz`, `friendlyfoods.co.sz` all NXDOMAIN on direct-guess probing. |

Eswatini is in the same Common Monetary Area / SACU bloc as Namibia and
South Africa and shows the identical pattern: the region's dominant grocery
chain (Shoprite) runs the same brochure-only corporate template with no
online ordering. No delivery marketplace (Jumia/Glovo/Bolt/Yango-style)
operates in Eswatini. WebSearch budget was exhausted session-wide before
this country could be searched properly (only direct-domain-guess probing
was possible) — treat as **inconclusive-leaning-negative**, not exhaustively
confirmed. A fresh WebSearch-based pass (once budget resets) is the clear
next step, specifically for SPAR/OK Foods Eswatini, which are real chains
with no domain found yet rather than confirmed non-existent online.
