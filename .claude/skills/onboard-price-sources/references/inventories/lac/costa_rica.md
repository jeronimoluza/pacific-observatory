# Costa Rica

_Inventory written: 2026-09-01_

LAC wave-13 sweep, agent B. Cold start — no `lac/costa_rica.md` inventory
existed before this file. Already covered before this pass: `automercado_cr`
(supermarket), `walmart_cr` (supermarket), `gollo_cr` (dept-store),
`unimart_cr` (dept-store) — 2 food / 4 total. No food source shipped this
pass — the best candidate (MegaSuper) was probed deeply but not completed;
see the writeup below, which is intended to let a future pass finish it in
well under an hour instead of re-discovering the platform from scratch.

| Source name | URL | Channel | Status | Notes |
|---|---|---|---|---|
| MegaSuper | https://www.megasuper.com/ | supermarket | **PROBED, NOT SHIPPED — feasible, needs more extraction work** | Independent chain (Corporación Megasuper, backed by Colombia's Grupo Olímpica — NOT Walmart, NOT AutoMercado). Runs on **Instaleap**, a headless grocery-commerce SaaS (`nextgentheadless.instaleap.io/api/v3`, a GraphQL gateway; public `dpl-api-key: 09e9a997-5c41-4460-8fe7-3fa37f9774f1` visible in every browser request, no further auth). `GetCategoryTree` query works cleanly with just `{clientId: "MEGASUPER", storeReference: "M102"}` and returns the full category tree (confirmed: top node `ABARROTES` path `/01`, `LÁCTEOS Y HUEVOS` path `/13`, etc.). **The blocker**: GraphQL introspection is disabled, and the actual product-search operation is called server-side during Next.js SSR — it never appears in the browser's own network tab, so it could not be sniffed directly this pass (tried: network capture on scroll/navigation, JS bundle grep across ~150 chunks including the category-route chunk — no `GetProduct`/`SearchProducts` query text found in any client bundle). **What DOES work**: `curl_cffi` (with `verify=False` — the site's TLS chain has a local-trust-store issue, not an expired/hacked cert; not a `known_blockers.md` case) against a plain category URL (e.g. `/ca/lacteos-y-huevos/13`) returns full SSR HTML with real prices server-rendered inline — e.g. confirmed live "LECHE CONDENSADA NESTLÉ LA LECHERA TEXTURA LIGERA 397 G" ₡890 (₡710 on promo). The product data is embedded across ~150+ small `self.__next_f.push([1,"..."])` React-Server-Components stream chunks that must be concatenated IN ORDER before parsing (unlike `lacolonia_ni`'s single-chunk case) — confirmed the concatenation approach recovers real `"name":...,"price":...` objects (92 of a stated 358 products in one sampled category recovered via `"name":"([^"]{3,120})","price":([\d.]+)` on the concatenated+unescaped blob), but (a) that 92/358 suggests only a first-page slice is SSR'd, the rest likely loads on scroll via the same unsniffed GraphQL call, and (b) a clean product identifier (EAN/reference) was NOT yet resolved for the un-promoted items — the `reference` field seen belongs to `PromotionV2` objects (format `<EAN>_M102_specialPrice`) which only exist for discounted items, not the general case. Next steps for a future pass: (1) try the `dpl-api-key` against a directly-guessed `GetProductsByCategory`-style operation name once introspection-bypass ideas are exhausted, or (2) invest in properly resolving the RSC `$xx` chunk-reference graph to pull `reference`/EAN alongside `name`/`price` for every product, not just promoted ones. PDP URLs are a clean `/p/<slug>-<ean13>` pattern (confirmed from homepage hrefs), which is a usable stand-in product_id source once the listing extraction is complete. |
| Compre Bien | https://comprebien.cr/ | — | **NOT PURSUED — Blazor WebAssembly, high effort** | Confirmed 100% independent, family-owned (Rojas Solórzano family, founded 1943, Palmares-based). Catalog at `/Tienda/TiendaPrincipal` is a client-rendered .NET Blazor WASM app (`MauiStore.Shared`) — no product data in raw HTML; would need the underlying REST/SignalR API reverse-engineered. Left for a future pass. |
| PriceSmart (Costa Rica) | https://www.pricesmart.com/es-cr | — | **NOT PURSUED — commerce API undetermined** | International warehouse-club chain, independent of Walmart/AutoMercado. Category pages exist but show no product/price data in fetched HTML; backend uses Bloomreach for content, real commerce API not identified this pass. |
| Mas x Menos / Palí / Maxi Palí / Mas x Menos Express | masxmenos.cr and banners | — | **DEAD END — confirmed Walmart Centroamérica banners, same company as `walmart_cr`** | Do not onboard. |
| Perimercados / Súper Compro / Saretto | — | — | **DEAD END — acquired by Walmart Centroamérica in 2024, now same company as `walmart_cr`** | Formerly independent Grupo Gessa chains; press coverage confirms the 2024 sale. Do not onboard. |
| Peridomicilio | https://peridomicilio.com/ | — | **SUSPECT same-company as Perimercados — NOT onboarded, unverified** | Name literally reads "Peri[mercados] a domicilio" and runs the identical Instaleap Next.js build (byte-identical asset hashes) under its own Instaleap tenant "PERI_DOMICILIOS". Given the Gessa→Walmart sale of Perimercados, plausibly the online arm of a now-Walmart-owned chain — flagged for manual confirmation before any future onboarding, not treated as a clean new source. |
| Vindi | — | — | **SUSPECT same-company as `automercado_cr` — NOT onboarded, unverified** | One search source states Vindi is an AutoMercado-owned convenience banner. Not independently confirmed this pass (WebSearch budget exhausted session-wide) — needs verification before ruling in or out. |
| Isleña Market Store | https://islenamarketstore.cr/ | — | **DEAD END — WhatsApp order funnel, no catalog** | Marketing front-end for Distribuidora Isleña (`di.cr`); pushes all orders to WhatsApp, no scrapeable web catalog. |
| SUKASA | https://sukasa.co.cr/ | — | **OUT OF SCOPE — home goods/furniture/appliances, not food** | |
| Rappi (Costa Rica) | https://rappi.co.cr/tiendas/tipo/market | — | **DEAD END — JS SPA shell, zero embedded product data; listed "supermercados" are all already-covered chains anyway (Walmart/Masxmenos/PriceSmart)** | |
| PedidosYa Market (Costa Rica) | https://pedidosya.cr/cadenas/pedidosya-market | — | **DEAD END — app-only, dark stores** | 403 on fetch; press coverage describes it as closed "Dmarts" not open to the public — same app-only pattern confirmed for El Salvador and Nicaragua's PedidosYa. |
| Uber Eats brand pages (AMPM, Fresh Market) | ubereats.com/cr/brand/... | — | **DEAD END — 403 bot-blocked, no independent web catalog** | AMPM/Fresh Market convenience stores deliver only through UberEats/Uber-Speed. |

## Outcome after this pass

Costa Rica stays at **2 food / 4 total** — no new source shipped, but
MegaSuper is a well-documented, credible near-miss (real independent chain,
platform fully fingerprinted, working curl-only access path, partial
extraction proven) that the next pass should be able to finish quickly using
the notes above rather than re-discovering Instaleap from scratch. Three
suspect same-company candidates (Peridomicilio, Vindi) need a cheap
confirmation check before being ruled in or out.
