# Nicaragua

_Inventory written: 2026-09-01_

LAC wave-13 sweep, agent B. Cold start — no `lac/nicaragua.md` inventory existed
before this file. Already covered before this pass: `launion_ni` (supermarket),
`walmart_ni` (supermarket), `lacuracaonline_ni` (electronics), `sinsa_ni`,
`wfp_prices` (shared regional `official_avg` fetcher) — 2 food / 5 total.

| Source name | URL | Channel | Status | Notes |
|---|---|---|---|---|
| La Colonia (Nicaragua) | https://lacolonia.com.ni/ | supermarket | **SHIPPED** as `lacolonia_ni` | A DIFFERENT platform build from the pre-existing `lacolonia_hn` (Honduras, VTEX) — same brand, but this Nicaragua storefront is Next.js (App Router). Each `/categoria/<slug>` page server-renders the whole category's product list as a JSON array (`initialProducts`) embedded in a React Server Components script payload — no separate API call, no pagination needed. 19 of 20 categories yielded data (TextilesJuguetes confirmed genuinely empty on the live site, `totalCount: 0`, not a parsing bug). Full unbounded run 2026-09-01: 5,970 rows, 5,970 distinct `product_id`/`url` (zero dupes), 0 blank names, 0 zero/negative prices, 100% NIO, price range C$3–C$4,392.50 (median C$135). Food/beverage/tobacco share (Abarrotes+LacteosHuevo+BebidasYGaseosas+BebidasAlcoholicas+Carnes+Embutidos+Panaderia+FrutasVerduras+Congelado+Cigarros) = 3,653/5,970 = 61.2% — clearly food-dominant, correctly `channel: supermarket`. 2/2 cold re-fetch spot checks (product codes 1520122, 4300031) matched name and price exactly. |
| PedidosYa (Nicaragua) | https://www.pedidosyani.com.ni/ | — | **DEAD END — restaurant-only web surface, no grocery catalog found** | Web root exposes only restaurant/food-delivery listing paths (same app-only-for-groceries pattern already confirmed for El Salvador's PedidosYa, wave 10). No `/supermercados` or `/mercado` web catalog located this pass. |
| tuNicaragua.com | https://tunicaragua.com/index.php/es/supermercado-la-colonia | specialty-food | **NOT PURSUED — appears to be a diaspora gift/remittance reseller of La Colonia's own catalog, not an independent retailer** | VirtueMart (Joomla) storefront explicitly named "Supermercado La Colonia" as its category — i.e. it resells La Colonia's products to a diaspora-gift audience rather than running its own catalog. Given `lacolonia_ni` was already shipped this pass (same underlying products, likely USD-marked-up for remote gifting), onboarding this too would double-count the same shelf under rule 10. Not probed further. |
| Walmart-Centroamérica banners (Palí / Maxi Palí) | (not individually probed) | — | **NOT PURSUED — same VTEX backend as `walmart_ni`** | Not named directly in search results this pass, but the Honduras check in this same wave (see `honduras.md`) confirmed Walmart Centroamérica reuses one VTEX product-ID namespace across its regional banners (Walmart HN == "Paiz" HN, byte-identical `productId`s). Given that confirmed pattern, any Nicaraguan Palí/Maxi Palí storefront is assumed same-shelf as `walmart_ni` unless a future pass finds evidence otherwise — not spending probe budget re-confirming per country. |

## Outcome after this pass

Nicaragua ends at **3 food / 6 total** sources (`launion_ni`, `walmart_ni`,
`lacolonia_ni` all `channel: supermarket`). One genuine new independent
supermarket chain found and shipped. PedidosYa confirmed app-only for
groceries (consistent with the regional pattern already documented for El
Salvador). tuNicaragua.com is a same-shelf reseller of La Colonia's own
catalog, not an independent source — correctly not onboarded.
