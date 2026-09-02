# Equatorial Guinea

_Inventory written: 2026-09-01_

SSA sweep, agent A. Cold-start: country had **zero manifests of any kind**
before this pass (not even a WFP/FEWS NET humanitarian fetcher) — confirmed
against `src/prices/configs/ssa/central_africa/equatorial_guinea/`, which
did not exist. Discovery for this country ran via a general-purpose research
subagent with full WebSearch access (session budget was not yet exhausted).
**Result: 1 source shipped, first-ever for this country.**

## Shipped

| Source key | Channel | `analytical_role` | Rows (full unbounded run) | Notes |
|---|---|---|---|---|
| `situcka_gq` | `marketplace` | `retailer_sku` | 6,931 | WooCommerce Store API (`situcka.com`, open, no auth). General multi-vendor marketplace for Malabo/Bata (restaurants, cosmetics, hardware, art, diet products), scoped via `CATEGORY_ID=24` to the "Supermercados" umbrella category only, which aggregates 6 distinct physical supermarket chains that otherwise have no online catalogue of their own — Martinez Hermanos (EG's largest chain, 4,123 products; its own site `martinezhermanos.com` is a dead brochure with 0 products/prices), Guinaco (2,556), Ecua Market (176), EGTC (16), Mangarams (14), Pegasos (16). Tagged `marketplace` rather than `supermarket` because the scoped category still spans multiple distinct operators. currency XAF, `currency_minor_unit=0` confirmed live (integer currency). 0 blank names, all 6,931 `product_id`/`url` distinct, only 3 rows (0.04%) had price=0 (real out-of-stock/unpriced items on the vendor's own site, not a scraping defect). Estimated food/beverage share (regex over category+name, Spanish + French vendor labels) ~42-45%, consistent with a full-basket supermarket catalogue (also carries higiene/limpieza/electrodomésticos, same as any real supermarket). Cold re-fetch of 2 products (`33909` rice, `4630` chicken wing) matched the stored name and price exactly.

## Dead ends

| Candidate | URL | Status | Notes |
|---|---|---|---|
| Jumia | jumia.com | **DEAD — no EG storefront** | Jumia's current active market list (~8-9 countries) does not include Equatorial Guinea. |
| Glovo | glovoapp.com | **DEAD — no EG storefront** | Active African footprint is 6 countries; EG absent. |
| Yango / Bolt Food / Wolt | — | **DEAD — no EG presence found** | No evidence of operations in EG. |
| Martínez Hermanos (own site) | martinezhermanos.com/sectores/supermercados/ | **DEAD — brochure site, 0 products** | Corporate store-locator page only. Full catalogue recovered instead via `situcka_gq` (see above). |
| Cofina / Congelados Fina | — | **DEAD — no discoverable entity/site** | No website or domain found under this name. |
| Comprá en Bata directory | compraenbata.com/tiendasvirtuales.php | **DEAD — directory only** | Lists a "Comestibles, Bebidas, Delicatessen" category with 5 listings but exposes no individual vendor URLs. |
| Supermercado Vitacana / Muankaban / Manolo / Tienda Ideal / EGTC (standalone) | local business directories | **DEAD — brochure/directory-only** | Address/phone entries only, no independent e-commerce site found (EGTC's products are recovered via `situcka_gq`'s Supermercados category instead). |
| PLASENCIA, SUPERCOR Malabo, La Vencedora Malabo | — | **DEAD — no discoverable entity** | No matching business found for EG under these names. |
