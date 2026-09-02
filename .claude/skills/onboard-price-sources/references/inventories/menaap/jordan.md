# Jordan — price source inventory (menaap/middle_east/jordan)

_Inventory written: 2026-09-01_ (wave 13)

Wave-13 brief: Jordan started this pass at 3 sources / 0 food
(`smartbuy_jo` electronics, `dos_cpi` cpi_benchmark, `wfp_prices`
official_avg). Target: >=5 sources AND >=2 food-and-beverage sources.
Supplied candidate list was a single useless row (DNA Lifestyle,
electronics) — this was a pure discovery pass. **Bar cleared**: two new
`channel: supermarket` retailer_sku sources onboarded (`cozmo_jo`,
`jcscc_jo`), landing at 5 sources / 2 food from this agent's work alone.
(A second, concurrently-running agent independently added a third grocer,
`sahel25_jo` — see note at the end; not built by this pass, left alone
mid-flight.)

## Onboarded this pass

| Source | URL | channel | Verified |
|---|---|---|---|
| `cozmo_jo` | cozmo.jo | supermarket | 6,254 rows, 0 dup product_id/url, 0 zero-price, 0 blank names, 100% JOD, median 3.25 JOD. ~69% food/beverage share (food-cupboard 2,486 + dairy-eggs-butter 406 + tea-coffee-soft-drinks 374 + frozen 302 + organic-free-from-shop 224+2 + deli 188 + bakery 126 + butchery 125 + fruits-vegetables 71 + ready-to-eat-meals 19 = 4,323 of 6,254). |
| `jcscc_jo` | jcsccshop.gov.jo | supermarket | 1,443 rows, 0 dup product_id/url, 0 zero-price, 0 blank names, 100% JOD, median 1.75 JOD. ~62% food/beverage share (groceries 438 + sweets 165 + beverages 123 + dairy/cheese/eggs 73 + frozen 45 + bakery/cake 37 + save-more promos 17 = 898 of 1,443; personal-care 258 + home-care 284 + heaters 3 are non-food). |

## Dead ends found this pass (record so the next run doesn't repeat them)

| Candidate | URL | Verdict | Notes |
|---|---|---|---|
| Carrefour Jordan | carrefourjordan.com | DEAD — business closed | Carrefour ceased ALL Jordan operations 2024-11-04 (BDS boycott campaign); the franchisee (Majid Al Futtaim) rebranded the same 34 stores as **HyperMax**. The old domain now resolves to an IP-Twins domain-broker parking page (`<title>IP Twins - This domain name is registered</title>`), confirming the brand is genuinely gone, not just DNS drift. |
| HyperMax (Carrefour's Jordan successor) | www.hypermax.com.jo | DEAD — Akamai, same MAF Gulf tenant | Same URL shape as the other MAF storefronts (`/mafjor/en/`, matching `carrefourqatar.com/mafqat/en`, `carrefouruae.com/mafuae/en`). HTTP 403 `Access Denied` / `errors.edgesuite.net` reference-id format `18.9dce4917.<epoch>.<hex>` on **all three** curl_cffi profiles (chrome124/chrome120/safari17_0) AND on headless Playwright (same signature) — genuine block per the mandatory two-lever gate. This is the **same Akamai tenant** already recorded in `known_blockers.md` for carrefourqatar.com/carrefourksa.com/carrefouruae.com/carrefouruganda.com — the MAF Gulf/Akamai backend evidently survived the Carrefour→HyperMax rebrand unchanged. Added to `known_blockers.md`. |
| Sameh Mall | samehmall.com (does not resolve); samehgroup.com | DEAD / wrong service | `samehmall.com` and `www.samehmall.com` both NXDOMAIN. `samehgroup.com` apex resolves but serves a bare `{"ok":true,"service":"php-otp",...}` JSON stub (an unrelated OTP microservice, not the mall's storefront); `www.samehgroup.com` fails TLS handshake entirely (`TLSV1_ALERT_INTERNAL_ERROR`) across all three curl_cffi profiles — server misconfiguration, not a WAF. Web search confirms no dedicated Sameh Mall e-commerce site exists; the chain is reachable only via Talabat delivery. |
| Miles Supermarket | miles.com.jo | DEAD — TCP timeout | Both `miles.com.jo` and `www.miles.com.jo` resolve to real IPs (5.135.77.214 / 161.97.82.184 — confirmed against 8.8.8.8, not a DNS lie) but the TCP connection itself times out (curl exit 28, 0 bytes) on both HTTP and HTTPS. Server not answering, not a bot-block. |
| C-Town Jordan | — | App-only, no web catalogue | Real Amman chain (Independence Mall, Abdali Mall, Amman Mall, Jabal Al-Hussein). Delivery/loyalty exists only via a dedicated iOS/Android app (`jo.ctown.ecom`); no standalone website found. |
| Talabat Mart (T-Mart) Jordan | talabat.com/jordan/tmart | Not pursued — needs address/session context | `__NEXT_DATA__` present but empty (`mostSellingItems: []`) with no branch selected; the real catalog only loads client-side after a delivery-address/geolocation step, which is a bigger lift than budget allowed this pass. Rule-14 named-merchant split (Talabat's own dark-store brand, not a third-party merchant) remains a legitimate future target if a session/address flow is worked out. |
| Kareem Hypermarket / Kareem Mall | kareemmall.net | DEAD — domain expired, now squatted | Redirects to `plano-towing.com`, an unrelated US towing-company site. Real chain (est. 2019, Talabat-listed as `kareem-market`/`kareem-hyper-market`) but no live first-party website. |
| Matjarii | matjarii.com | DEAD — origin down | HTTP 522 (Cloudflare "connection timed out to origin") on all three curl_cffi profiles — a real Cloudflare-fronted site whose backend is not answering, not a WAF block. Self-described as "the largest e-commerce site in Jordan" with a grocery/supermarket category (`/supermarket/grocery.html`) — worth a re-probe in a future wave in case the origin comes back. |
| Zad (زاد) | zadfresh.com | DEAD — unconfigured server | Returns the stock "Welcome to nginx!" placeholder page — domain registered, web server installed, nothing deployed. |
| Basket.Jo | basket.jo, www.basket.jo | DEAD — domain does not resolve | App Store listing exists ("Basket App - Grocery Shopping") but no matching website; NXDOMAIN on both apex and www. |
| Jet Grocery | jetapp.me | App-marketing page only, no web catalogue | 200 OK, ~3MB single-page app-download landing site (`#downloadSec` anchor, base64-embedded screenshots) — no product listing or price rendered server-side; the real catalog is app-only. |
| Zait & Zaatar | zaitandzaatar.com | Not pursued — likely a restaurant, not a grocer | Amman-based (Al Shmaisani), online ordering exists (`/online-order/`), but every description found frames it as a Lebanese-food eatery/deli, not a supermarket — didn't probe further given the channel-mislabeling risk this brief explicitly warns against (rule: "do not relabel a pharmacy as specialty-food to clear the bar"). |
| Safeway Jordan | — | Structural — no standalone website | Real 16-store chain (200k+ loyalty members) but reachable only via Talabat/Ubuy/ClicFlyer third parties; no first-party e-commerce site found. |
| JCSCC — Fresh Meat & Poultry division | jcsccshop.gov.jo, mainCat=66584 | Residual gap — empty at top-level id | The one JCSCC top-level division that returned ZERO product cards at its flat `mainCat` id (confirmed: real HTTP 200, valid page shell, 0 `productId` matches) while the other 10 top-level ids all returned real product listings. Likely requires walking sub-category ids instead of the flat parent id — not pursued further this pass (already had food-share bar cleared without it). Worth a follow-up if finer JCSCC coverage is wanted. |

## Concurrent addition (not built by this pass)

While this pass was mid-flight, another agent in the same shared checkout
independently added **`sahel25_jo`** (sahel25.com, Amman-only grocery
delivery, Tier-2 Playwright-rendered React/Vite SPA, `channel: supermarket`,
1,835 products discovered via sitemap) — config and spider file are on disk
but no test run had completed as of this writing. Left untouched
deliberately to avoid colliding with in-progress work; if it lands cleanly
Jordan would sit at 6 sources / 3 food rather than 5/2.

## Method notes

- JOD 3-decimal trap checked explicitly on both onboarded sources (see
  `cozmo_jo.yaml` / `jcscc_jo.yaml` notes) — parsed floats matched the
  site's own displayed price strings exactly in every cold re-fetch;
  no minor-unit scaling was needed on either site (both display the JOD
  amount directly as decimal text, not integer fils).
- Both onboarded storefronts are single-language (`cozmo_jo` English-only,
  `jcscc_jo` Arabic-only) — no WPML/Polylang duplicate-catalogue risk
  (rule 21) observed on either.
- Search budget: used Arabic-language search only where English leads ran
  out (per rule 2); several Arabic queries using "عمان" returned Oman
  results instead of Amman due to the shared spelling — worth remembering
  for future MENA passes, prefer "الأردن" (Jordan) or "الاردن" alongside
  "عمان" to disambiguate.
