# Iran — price-source inventory

_Inventory written: 2026-09-28_

## Coverage before this pass (2026-09-15 trusted build)

25 manifests existed under `src/prices/configs/menaap/middle_east/iran/`, almost all
`channel: cosmetics` or `channel: pharmacy` WooCommerce stores (adibmarket_ir,
anjelagallery_ir, arayeshishahin_ir, azzaro_perfume_ir, bizma_ir, celineshops_ir,
chawan_ir, doctornice_ir, drluxe_ir, drsalem_ir, dubaik_ir, ellbeauty_ir, golsima_ir,
hami_ir, hoshmandshop_ir, irajgallery_ir, khayamdaru_ir, mahak_cosmetic_ir), plus
khajikala_ir (home-improvement/building materials), hastmarket_ir and royalnuts_ir
(food), sheypoor_ir (classifieds marketplace, aggregate), torob_ir (price-comparison
aggregate_proxy), and wfp_prices (fetcher, official_avg food). Despite the count, the
2026-09-15 trusted build reported only 1 COICOP division populated at trust-worthy
volume (12,449 rows across 14 trusted sources) — the cosmetics/pharmacy cluster
dominates and most of it likely lands in a single division. No fashion, electronics,
household-appliance, or tariff/utility source existed before this pass.

## Shipped this pass (w40, 2026-09-28)

| Source | Channel | analytical_role | Divisions opened |
|---|---|---|---|
| `dominokala_ir` | electronics (home appliances) | retailer_sku | 05 |
| `iranian_style_ir` | fashion | retailer_sku | 03 |
| `itmall_ir` | electronics (consumer: phones/laptops/powerbanks) | retailer_sku | 05/09 |
| `mci_tariff` | null (tariff) | tariff | 08.3 |

## Dead ends this pass

| Host | Verdict | Lever | Tell |
|---|---|---|---|
| javan-electronic.ir | no_catalog | curl_cffi:chrome124 | open WooCommerce Store API, every sampled item price=0 — a B2B quote-on-request fiber-optic/dev-board distributor, not consumer retail |
| tavanir.org.ir | unreachable | curl_cffi:chrome124 | connection timeout after 25s — national electricity transmission company (Tavanir); consistent with the country-wide IP-fence tell already on file for shahrvand.ir/hyperstar.ir/etka.ir/mahanmarket.ir (2026-09-05 migration rows) |
| my.nigc.ir | unreachable | curl_cffi:chrome124 | connection timeout after 25s — same geo-block tell |
| aepdc.ir | unreachable | curl_cffi:chrome124 | connection timeout after 25s — same geo-block tell (Azarbaijan regional electricity distribution co.) |
| atramart.com | blocked | curl_cffi:chrome124 | HTTP 403, `noindex` robots meta |

## Probed but not pursued (needs_work — viable, budget-limited)

| Host | Why not pursued | What it looked like |
|---|---|---|
| nigc-gl.ir | Budget — already had a tariff source (mci_tariff) | National Iranian Gas Co. (Gilan province) — clean 200, has a residential gas-tariff page at `/Fa/DMenu/17079/روش-محاسبه-و-تعرفه-گاز-مشترکین-خانگی`. Good next-pass fetcher for COICOP 04.5.2 (gas). |
| banimode.com | Custom platform (wp-json 404s), ARCAPTCHA widget present on page | Major Iranian fashion e-commerce; homepage 200s clean over curl_cffi, would need Playwright network-capture to find its real product endpoint |
| digistyle.com | 5.7 KB homepage body — SPA shell, not server-rendered | Digikala's fashion vertical; would need Playwright render before it's assessable |
| digikala.com | Not probed past homepage (13.5 KB body, likely SPA/challenge) | Iran's largest marketplace — per skill doctrine, a marketplace is a directory, not a source; its seller list would be the real prize, not scraping it directly |

## Notes

- **Toman vs Rial convention confirmed again**: every WooCommerce store hit this pass
  (dominokala, iranian-style, itmall) reports `currency_code: "IRT"` — the established
  repo-wide fix (`FORCE_CURRENCY="IRR"`, `PRICE_MULTIPLIER=10`) applies unchanged.
- **mci.ir does NOT follow the Toman convention** — its tariff tables are natively
  Rial-denominated (labelled "(ریال)" in the header), so `mci_tariff.py` applies no
  multiplier. Worth flagging explicitly since every other Iran source this pass needed
  the x10 correction.
- **Geo-blocking tell for Iranian institutional/utility hosts is a connection timeout
  (curl_cffi hangs ~25s), not an HTTP 403** — distinct from the retail WooCommerce
  stores, which are all openly reachable. Consistent with the 2026-09-05 migrated rows
  for shahrvand.ir/hyperstar.ir/etka.ir/mahanmarket.ir (those showed `http-403` +
  Incapsula, a different tell — so Iranian geo-blocking isn't one uniform signature;
  expect either a hang or a 403+challenge depending on the host's CDN).
- **countries.yaml problem**: `iran.languages: [en]` is wrong — Iran is overwhelmingly
  Persian-language commerce (every source onboarded here and previously is `fa`).
  `_resolve_lang()` falls back to the country's first `languages:` entry, so any fetcher
  or spider that omits its own `language:` field would silently get `"en"` for Iran.
  Every manifest onboarded this pass sets `language: fa` explicitly to route around it,
  but the underlying `countries.yaml` entry should be fixed to `languages: [fa]` (matches
  the CLAUDE.md-documented class of bug: English listed first for non-English-dominant
  countries).

## Next gaps to target (priority order)

1. **Fuel retail (COICOP 07.2.2)** — no gasoline-price source exists for Iran at all;
   `gheymat.live` and `setare.com` surfaced in this pass's sweep as possible live
   fuel-price trackers, not yet probed.
2. **Gas/electricity/water tariffs (04.5)** — `nigc-gl.ir` (gas) is a ready lead;
   `tavanir.org.ir` (electricity, national) and `aepdc.ir` (electricity, regional) are
   geo-blocked from this IP and need an in-country vantage point or a different lever.
3. **Furniture/household durables (05)** — iblo.ir, moblomiz.com, shahrmobleman.com,
   irandecor.com surfaced in the sweep, not probed this pass.
4. **CPI benchmark (cpi_benchmark)** — no Iran NSO/SCI (Statistical Centre of Iran) CPI
   feed exists yet; would need its own fetcher pass.
