# Venezuela

_Inventory written: 2026-09-01_

Wave 7 pass. Cold start — no `lac/` inventory existed for Venezuela before this file
(only `cuba.md` existed in this directory, from a concurrent wave-7 agent). Already
covered before this pass: `farmatodo_ve` (pharmacy, VES), `mafabre_ve` (supermarket,
USD), `paotrolado_ve` (supermarket, USD) — 3 sources / 2 food. Verified directly against
`outputs/sources_pending_jero.xlsx`: no Venezuela/VEN row anywhere in any of the six
sheets (Summary, Pending sources, Country coverage, P1 ZERO-source countries, P2 1-2
sources, NO CANDIDATES - discovery), confirming the brief's "no workbook candidates"
claim. This pass needed 2 more sources of any channel; target was >=5 sources AND >=2
food.

Venezuela's currency situation is genuinely bifurcated across retailers, not a single
convention: some storefronts (farmatodo_ve, locatel_ve — this pass) price natively in
VES (the shelf price is a bolivar figure that a BCV-rate PDP widget separately converts
to an *informational* USD equivalent); others (mafabre_ve, paotrolado_ve, multimax_ve —
this pass) are fully dollarized and never mention VES/Bs./BCV anywhere on the page.
Neither is a data-quality bug — record whichever currency each site's own JSON-LD /
rendered shelf price actually states, and never assume one from `countries.yaml`
(VES) or from the brand being Venezuelan.

| Source name | URL | Channel | Status | Notes |
|---|---|---|---|---|
| Locatel | https://www.locatel.com.ve/ | pharmacy | **SHIPPED** as `locatel_ve` | VTEX tenant (`accountName: locatelvenezuela`), independent of the Cencosud/Walmart-CA VTEX cluster. `/api/catalog_system/pub/category/tree` -> 219 leaf categories (mostly Farmacia/Cuidado Personal/Equipos Medicos/Dermocosmeticos, plus small Alimentos and Hogar branches). Page-0-vs-page-50 disjoint-set enumerability confirmed on a live leaf category before scaffolding. Currency is genuinely VES: `commertialOffer.Price` matches the PDP's schema.org JSON-LD `priceCurrency: "VES"` exactly, and the rendered price shows a `Bs.S` currency literal. The PDP additionally renders a secondary `PrecioUSD` block (`custom-price-ven-usd-summary`) tied to "tasa BCV" language elsewhere on the page — a USD-equivalent shown for reference/free-shipping-threshold purposes only, not captured; no on-site statement of Locatel's own VES repricing cadence was found (checked FAQ/T&C/pricing-policy pages), so treat the VES figure as this site's stated shelf price at scrape time, not confirmed-sticky vs confirmed-daily-repegged. Full unbounded run 2026-09-01: 10,682 rows, 10,682 distinct `product_id`/`url` (zero dupes), 0 zero/negative price, 0 blank name, 100% VES, price range Bs 0.71–2,859,515.43 (median Bs 5,567.98), category composition Farmacia 4,285 / Cuidado Personal 2,566 / Alimentos 1,582 / Equipos Medicos 967 / Cuidado Del Bebe 392 / Dermocosmeticos 331 / Hogar 324 / Nutricion Especializada 235 — pharmacy/health-and-beauty dominant (~54% Farmacia+Equipos Medicos+Dermocosmeticos+Nutricion), correctly `channel: pharmacy` despite a real 14.8% Alimentos branch (same judgment call as the pre-existing farmatodo_ve). The largest single leaf (Farmacia > MEDICAMENTOS > MEDICAMENTOS, 2,548 rows) topped out at 52 of the `_vtex_base` cap's 60 pages — **no leaf hit the 3,000-item-per-leaf cap**, so this is a complete catalog walk, not a truncated one. 3/3 cold re-fetch spot checks matched exactly. |
| Multimax | https://www.multimax.com.ve/ | dept-store | **SHIPPED** as `multimax_ve` | Custom Astro storefront — no VTEX/Shopify/WooCommerce/Magento fingerprint. Category listing pages (e.g. `/electrodomesticos`) render inline but expose no pagination control or API call, so scaffolded against `sitemap.xml` -> `sitemap-productos.xml`, which lists 3,605 distinct `/producto/<slug>` URLs directly (not a shard index — real product URLs). Each PDP embeds a schema.org `@graph` JSON-LD block with `Product` + sibling `BreadcrumbList` nodes; category built from the breadcrumb trail since the Product node has no bare `category` field. Currency confirmed USD (JSON-LD `priceCurrency: "USD"`) with zero VES/Bs./BCV mentions anywhere on a sampled PDP — a straightforwardly dollarized appliance/electronics/home-goods/hardware/apparel retailer, same pattern as mafabre_ve/paotrolado_ve. Full unbounded run 2026-09-01: 3,605 rows, 3,605 distinct `product_id`, 3,605 distinct `url` (zero dupes), 0 zero/negative price, 0 blank name, 100% USD, price range $0.50-$5,528.99 (median $51.99), dominant categories Ferreteria/Herramientas, Variedades/Perfumes, Hogar/Muebles, Calzado, Electrodomesticos — 0% food share by category-keyword scan, consistent with `channel: dept-store` (correctly not counted toward the food bar). 3/3 cold re-fetch spot checks matched exactly on name and price. |
| Traki | https://www.tiendastraki.com/ (redirects to traki.com) | — | **DEAD (for now) — site in maintenance mode** | `traki.com` and `traki.com.ve` both resolve and return HTTP 200, but the entire site serves a "Estamos en mantenimiento" (under-maintenance) holding page with only a WhatsApp contact link — no catalog, no product markup at any layer. Not a WAF/bot block; a genuine temporary outage. Worth a cheap re-check in a future pass since the domain and brand are otherwise live. |
| Excelsior Gama | https://www.excelsiorgama.com/, excelsiorgama.com | — | **DEAD — host unreachable** | `excelsiorgama.com` resolves via DNS (200.74.202.99) but refuses TCP connections on both port 443 and port 80 (`curl_cffi` "Could not connect to server" on both, ~7s each). `www.excelsiorgama.com` and `.com.ve` variants don't resolve at all. Not a WAF — nothing is listening. |
| Central Madeirense | centralmadeirense.com.ve, www.centralmadeirense.com | — | **DEAD — no reachable domain found** | `centralmadeirense.com.ve` (no `www.`) does not resolve (NXDOMAIN); `www.centralmadeirense.com.ve` connection-times-out at the TCP layer (28s); `www.centralmadeirense.com` resets the connection mid-handshake. No working entry point found across three domain variants. |
| Automercados Plaza's | automercadosplazas.com, .com.ve, plazas.com.ve | — | **NOT REACHABLE — no working domain found** | None of the tried variants resolve (NXDOMAIN on all). Not pursued further via search given the "any channel" bar was already cleared by Locatel + Multimax. |
| Beco | https://www.beco.com.ve/ | — | **DEAD — broken origin (expired TLS cert + 502 from the CDN over plain HTTP)** | `https://beco.com.ve/` fails TLS handshake with an expired certificate (curl error 60); falling back to plain `http://beco.com.ve/` gets past DNS/TCP to an nginx edge that returns a bare `502 Bad Gateway` — the origin behind the CDN/proxy is down, not a bot wall. Per rule 13 (expired cert -> record dead), not pursued further. |
| EPA (home improvement) | epaonline.com, epaonline.com.ve, epa.com.ve | — | **DEAD — domain repurposed as an ad-tech redirect page** | `www.epaonline.com` resolves and returns HTTP 200, but the page is a `2gnc.com`/`cheq` ad-tracking fingerprint-and-redirect stub (loads a `sd559908.js.2gnc.com` script, builds a fingerprint payload, then `window.location.replace`s to a tracked query string) — not the EPA hardware-chain storefront. `.com.ve` and bare `.ve` variants don't resolve. The real EPA Venezuela storefront domain (if one exists) was not found this pass. |

## COICOP / channel gap after this pass

Venezuela ends at **5 sources / 2 food** (`mafabre_ve` supermarket + `paotrolado_ve`
supermarket unchanged from before this pass), clearing both the 5-source and 2-food
bars exactly. Both new sources this pass (`locatel_ve` pharmacy, `multimax_ve`
dept-store) are non-food by the brief's definition and do not add food-channel
coverage, though locatel_ve's small "Alimentos" branch and multimax_ve's kitchenware
categories add incidental COICOP breadth outside 01.

Of the eight leads named in the brief, two shipped (Locatel, Multimax), one is a
genuine temporary outage worth a cheap recheck (Traki), and five are dead this pass
for structural reasons (unreachable host, no resolvable domain, broken origin, or a
repurposed ad-redirect domain) rather than anti-bot blocks — none of the five required
`known_blockers.md` treatment since none showed a WAF/CDN challenge signature.
