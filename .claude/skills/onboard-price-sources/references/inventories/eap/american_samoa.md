# American Samoa

_Inventory written: 2026-09-01_

Wave 11: needed 2 food-and-beverage sources against a baseline of 0. Result:
**1 built (costuless_flyer_as, channel hypermarket)**, 1 short of the target.
Every other lead investigated (local supermarket chains, the beverage
distributor, the two government sites) turned out to be a genuine dead end
for this pipeline -- see rows below. American Samoa's digital retail
footprint outside Cost.U.Less is essentially Facebook-only.

| Source name                                   | URL                                                              | COICOP divisions covered | Source type                        | Cadence      | Auth required? | Machine-readable?          | Anti-bot risk | Wayback coverage | Per-SKU IDs? | Notes |
| ---------------------------------------------- | ----------------------------------------------------------------- | ------------------------- | ----------------------------------- | ------------ | --------------- | ---------------------------- | -------------- | ----------------- | -------------- | ----- |
| Cost.U.Less American Samoa (BUILT: `costuless_flyer_as`) | https://www.costuless.com/american-samoa/flyers            | 01 (mixed grocery/household) | Warehouse-club weekly circular   | Weekly       | No              | Yes, indirectly              | Low (Playwright only) | No               | No (name-slug synthesised) | Physical store confirmed in Pago Pago (Ottoville Center). No e-commerce catalogue exists (no shop.*/order.* subdomain). The `/flyers` page embeds 2-3 rotating Flipsnack flipbook circulars; page IMAGES are not machine readable, but Flipsnack extracts each page's PDF text server-side into a short-TTL signed CloudFront JSON reachable only via a rendered browser. Spider renders each flyer with scrapy-playwright, captures that JSON via a response-event handler, and only accepts a "NOW $X.XX" chunk when exactly one product-quantity marker precedes it -- ambiguous multi-item blocks (common on 2-column produce/meat pages) are dropped rather than guessed. Verified live 2026-09-01: 24 clean rows from the concurrently-live General Mills + Kellanova brand inserts; the produce/meat/furniture circular parsed to zero rows and was correctly dropped. Row count and which flyers survive will vary week to week. |
| KS Mart (Tafuna)                              | https://www.facebook.com/p/KS-Mart-100057793774143/               | --                         | Local grocery chain                 | --           | --               | No -- Facebook page only, no website found | -- | -- | -- | Long-running local grocer (25+ yrs), Ilili Rd, Tafuna. No dedicated website found via direct probing or search; Facebook is the only online presence. DEAD. |
| TSM Mart (Tafuna)                             | https://www.facebook.com/TSM-Mart-249827675411060                 | --                         | Local grocery/variety chain          | --           | --               | No -- Facebook page only | -- | -- | -- | Two-story grocery + variety store, Route 014, Tafuna. No website found. DEAD. |
| Forsgren (Laufou Shopping Center, Nu'uuli)    | (none found)                                                       | --                         | Local variety/general store          | --           | --               | No                            | -- | -- | -- | forsgrens.com resolves but is an unrelated web-marketing-links squat domain, not the retailer. No other domain found via search. Per the American Samoa Pocket Guide, this store is "better for variety merchandise than food" regardless. DEAD (no site; marginal food fit even if found). |
| GHC Reid & Company (Tafuna Industrial Park)   | https://www.ghcreid.com/                                           | 01.2.2 (beverages only, if it counted) | Beverage distributor + WooCommerce storefront | -- | Effectively yes (see note) | JSON-LD prices present but hidden on the rendered page | Low | -- | Yes (WooCommerce SKUs) | WordPress/WooCommerce site with a real `/product/` catalog (~100 beverage SKUs: Coca-Cola family, Vailima beer, Dasani/Fiji water, Hawaiian Sun, Paul's milk, etc.), all sold in wholesale case packs (x24, x12, x8...). The `helios-solutions-woocommerce-hide-price-and-add-to-cart-button` plugin blanks the visible price (`<p class="price"></p>`) and hides add-to-cart for guests -- a classic B2B/wholesale gate; prices only leak via the raw `schema.org` JSON-LD. Genuinely a beverage wholesaler, not a retail storefront -- does NOT satisfy the "genuinely retail" bar the brief sets for distributors. DEAD for the food count (correctly wholesale, matches brief's own caution about this lead). |
| American Samoa Dept of Commerce -- store-level price survey | https://www.doc.as.gov/stats (Wix FAQ widget API)     | --                         | --                                    | --           | --               | --                            | -- | -- | -- | Checked all 5 FAQ categories in the same Wix widget that already backs `doc_bfi`/`doc_cpi` (General Data & Statistics, Basic Food Index, Consumer Price Index, BEAD Resources, Setting up FAQs) -- no store-level/per-retailer price table exists beyond the already-onboarded territory-wide BFI average. DEAD END (confirmed empty, not just unsearched). |
| American Samoa Dept of Agriculture / Fagatogo public market | https://www.doa.as.gov/                                | --                         | Public produce market                | --           | --               | No                            | -- | -- | -- | Site returns a "CloudAccess.net" hosting-lapsed placeholder page (cert also mismatches the hostname) -- the DOA website is effectively dead/unhosted. Fagatogo Market itself (the only traditional produce market, per the AS Pocket Guide) has no digital price presence anywhere found. DEAD END. |
| Samoa Market / Gounders Samoa / Frankie Samoa | samoamarket.com, gounderssamoa.com, frankiesamoa.com               | --                         | Online grocery delivery              | --           | --               | --                            | -- | -- | -- | LOCALITY TRAP: these serve independent Samoa (the nation), not American Samoa (the US territory) -- different country, different currency (WST). Not candidates here. |
| Uber Eats / DoorDash in American Samoa        | --                                                                  | --                         | Delivery marketplace                  | --           | --               | --                            | -- | -- | -- | No evidence either platform operates in American Samoa; search results only returned Samoa, CA (a US mainland place name collision) and Hawaii. No qualifying source found. |
| StarKist cannery outlet                        | --                                                                  | --                         | Cannery / manufacturer                | --           | --               | --                            | -- | -- | -- | Pago Pago cannery is a manufacturing plant (largest StarKist plant, ~80% of AS export revenue), not a retail outlet; no tours, no local outlet store, no online store scoped to American Samoa. Not a candidate. |

## COICOP coverage after this run

Only division 01 (food/beverage) gained coverage this wave, via
`costuless_flyer_as` (retailer_sku, weekly promotional snapshot, not a full
catalogue). All other divisions remain as they were before this run --
`doc_bfi`/`doc_cpi` (01, index + official_avg), `astca_prepaid_as` /
`bluesky_prepaid_as` (08, tariff), `malaeimi_wholesale_as` (wide, wholesale
channel, does not feed the retail food count).

## Outcome vs. brief

Final: **7 sources / 1 food** for American Samoa (was 5/0). Target was
>=5 sources AND >=2 food -- the source-count bar was already met before this
run; the food bar is short by one. Every lead in the brief's own priority
list was checked (Cost.U.Less: built; KS Mart, Forsgren's, Laufou tenants:
Facebook-only or no site; GHC Reid: genuinely wholesale, hidden prices; DOC
store-level survey: confirmed does not exist). This is reported as an honest
shortfall per the brief's explicit allowance, not a padded count.
