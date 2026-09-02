# Lebanon — price source inventory (menaap/middle_east)

_Inventory written: 2026-09-01_

Cold-start inventory. Lebanon started this pass at 2 food sources (`spinneys_lb`, `tripolimarket_lb`, both supermarket) plus `apharmasolutions_lb` (pharmacy) and `ishtari_lb` (dept-store).

## Onboarded this pass

| Source | Channel | Platform | Notes |
|---|---|---|---|
| `dapies_lb` | supermarket | WooCommerce Store API | "Online Grocery Store in Lebanon \| Fresh & Healthy Groceries" — a healthy/organic-food-focused grocer (dedicated fruit/veg/dairy/grains/spices/nuts categories, near-100% food by category). Standard `/wp-json/wc/store/v1/products`, no auth. USD, currency_minor_unit=2. 535 rows, 0 blank names, 0 zero/negative prices. Cold-refetched 2/2 products directly against the live Store API by product id — both name and price matched exactly. |

## Candidates probed and rejected

| Candidate | URL | Verdict | Notes |
|---|---|---|---|
| Faddoul Supermarket | faddoulsupermarket.com | DEAD — compromised/malware-injected | Found via a Bahrain search too (generic search noise) but the domain itself has no country signal checked; regardless, injected malware script disqualifies it outright. See `known_blockers.md`. |
| Al Mufeed Trading | almufeedsa.com | REJECTED — wrong country | Appeared in a Lebanon search ("سوبر ماركت لبنان") but is a Saudi Arabia company (Zid platform, `hreflang=ar-sa`, page text says "السعودية"). Worth revisiting for Saudi Arabia. |
| Le Charcutier | lecharcutier.com | NOT COMPLETED | 902KB `/shop/grocery-foods` page — genuinely large and real. Platform fingerprint was inconclusive (a "magento" string hit is likely a false positive; `/rest/V1/products` returned HTTP 500, not a clean Magento REST response). Worth a dedicated Playwright network-trace pass. |
| Clickomart | www.clickomart.com | NOT COMPLETED | 1.2MB homepage — large, real. Next.js signal detected; "magento" string hit likely a false positive (same as Le Charcutier). Not fingerprinted past the homepage. |
| Issa Trading (Super Market Issa) | issatradinglb.com | NOT COMPLETED | 1.1MB homepage — large, real. Same Next.js/ambiguous-Magento-string signal as Clickomart/Le Charcutier; worth checking whether these three share one platform vendor. |
| Metro Market | metromarketlebanon.com | NOT COMPLETED | Custom AngularJS/Cordova-derived web app (`config/config.js`, `cordovaneeds.js`) — same exact asset filenames as Promarché below, strongly suggesting one shared white-label vendor serving multiple Lebanese grocery brands. Needs a Playwright network trace to find the underlying API; not attempted this pass given the cost of today's earlier Playwright debugging on `sahel25_jo`. |
| Promarché | promarche.com.lb | NOT COMPLETED | Same AngularJS/Cordova codebase as Metro Market (identical `config/config.js`/`cordovaneeds.js` asset paths) — likely the same vendor. See Metro Market note; probe one to unlock a template for both. |
| Dukkani | dukkani-lb.com | DEAD (curl-only) — 403 on 3 TLS profiles | 403 on curl_cffi chrome124/chrome120/safari17_0. NOT yet checked with Playwright (the mandatory curl-AND-Playwright gate before calling this a genuine block was not completed this pass) — treat as a hypothesis, not a confirmed block. |
| Carrefour Lebanon | www.carrefourlebanon.com | DEAD — Akamai (MAF tenant, pre-documented) | `/maflbn/en` URL shape confirms the same Majid Al Futtaim Akamai tenant as the QA/SA/AE/JO/UG Carrefour properties already in `known_blockers.md`. Not re-probed. |

## Dead ends worth remembering

- **A cluster of three large (900KB–1.2MB), apparently-real grocery sites (Le Charcutier, Clickomart, Issa Trading) were found but not completed this pass** — each returned a "magento" string match that turned out to be unreliable (one gave HTTP 500 on the real Magento REST path), so the actual platform is still unidentified. This is the single best lead for the next Lebanon pass: fingerprint these three properly (check for `/pub/static/`, `Mage-Cache-Storage` cookie, or run a Playwright network trace) before assuming Magento.
- **Metro Market and Promarché share one white-label AngularJS/Cordova vendor** (identical asset filenames) — cracking either one likely unlocks both, and possibly other Lebanese grocery brands running the same stack. Worth a dedicated Playwright-discover pass.
- **The MAF/Carrefour Akamai tenant now covers Lebanon too** (`carrefourlebanon.com/maflbn/en`) — 6 confirmed countries on this one tenant (QA, SA, AE, UG, JO, LB).
