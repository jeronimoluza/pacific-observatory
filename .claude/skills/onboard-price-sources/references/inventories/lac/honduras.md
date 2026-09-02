# Honduras

_Inventory written: 2026-09-01_

LAC wave-13 sweep, agent B. Cold start — no `lac/honduras.md` inventory existed
before this file. Already covered before this pass: `lacolonia_hn`
(supermarket), `walmart_hn` (supermarket), `diunsa_hn` (dept-store),
`jetstereo_hn` (electronics), `lacuracaonline_hn` (electronics) — 2 food / 5
total. No food source shipped this pass — every lead found was either a
confirmed duplicate or a brochure site — but the duplicate check below is a
real finding that should save the next pass probe budget.

| Source name | URL | Channel | Status | Notes |
|---|---|---|---|---|
| Paiz (Honduras) | https://www.paiz.com.hn/ | — | **DEAD END — CONFIRMED same shelf as `walmart_hn`, do not onboard** | VTEX tenant, asset host `paizhn.vtexassets.com`. "Paiz" is normally Walmart Centroamérica's Guatemala banner name (already onboarded as `paiz_gt`), but Walmart CA also runs a Honduran storefront under this same brand name. Directly compared both APIs: `walmart.com.hn` and `paiz.com.hn` `/api/catalog_system/pub/products/search?_from=0&_to=9` return IDENTICAL `productId`+`productName` pairs (37268 "Banano Maduro Selección Especial...", 9829 "Huevo Marketside...", 87 "Culantro Castilla Mazo...", 69 "Zanahoria Suelta Libra..." — all four match exactly). Confirms Walmart Centroamérica reuses one VTEX product-ID namespace across country-level re-skins, not just cross-country banners — a new duplication pattern worth checking whenever a "different-named" chain turns out to also be VTEX in a country where `walmart_<cc>` already exists. |
| Comisariato Los Andes | https://comisariatolosandes.com/ | — | **DEAD END — brochure site, 0 products** | Confirmed Honduras-based (+504 phone prefix). Category banners for produce/meat/bakery/deli/liquor render, but no actual product cards or prices anywhere on the page — informational front-end only, images hosted on a bare S3 bucket. |
| Súper Fácil y Rápido | http://superfacilyrapido.weebly.com/ | — | **DEAD END — Weebly brochure site** | Tegucigalpa-only delivery service; no product catalog, no prices, contact-only page. |
| Supermercados Del Corral | https://super-del-corral.myshopify.com/ | — | **NOT CONFIRMED HONDURAS — not pursued** | Real live Shopify storefront, but no evidence found this pass that it operates in Honduras specifically (name pattern "Del Corral" is common to several LatAm markets); would need country confirmation before onboarding. Left for a future pass. |
| PedidosYa (Honduras) | (not separately probed) | — | **ASSUMED app-only per regional pattern, not directly re-confirmed** | El Salvador's PedidosYa Market vertical was confirmed app-only (wave 10); Nicaragua's was re-confirmed app-only this same pass. Honduras not separately probed given time budget — assume same pattern unless a future pass finds otherwise. |

## Outcome after this pass

Honduras stays at **2 food / 5 total** — no new food source. The Paiz
duplication finding is the useful output: it extends the known
Walmart-Centroamérica same-shelf pattern (previously documented as
cross-country banner reuse, e.g. Despensa Familiar/Maxi Despensa in El
Salvador and Guatemala) to a SAME-COUNTRY re-skin under a different brand
name. Any future "new Honduran supermarket" candidate that turns out to be
VTEX should be product-ID-compared against `walmart_hn` before onboarding.
