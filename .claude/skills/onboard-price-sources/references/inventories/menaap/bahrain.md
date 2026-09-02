# Bahrain — price source inventory (menaap/gulf_states)

_Inventory written: 2026-09-01_

Cold-start inventory. Bahrain started this pass at 2 food sources (`aljazira_bh`, `lulu_bh`, both supermarket/hypermarket) plus `jarir_bh` (electronics) and `nasser_pharmacy_bh` (pharmacy).

## Onboarded this pass

| Source | Channel | Platform | Notes |
|---|---|---|---|
| `megamart_bh` | supermarket | Server-rendered Django (django-oscar), `/en/catalogue/category/<path>_<id>/` listing pages | Large genuine online supermarket. 501 category/subcategory URLs discovered from the homepage nav; category listing pages render product name+price+url directly (no PDP visit needed), each page states its own "X of Y Products" total for pagination. **21,076 rows** (full unbounded run), 0 blank names, 0 zero/negative prices, 100% BHD (3 decimals, e.g. "0.550"), 353 distinct category leaf labels, food-ish share ≈81% by a keyword heuristic over categories. Cold-refetched 2/2 products, both matched live exactly. |

## Candidates probed and rejected

| Candidate | URL | Verdict | Notes |
|---|---|---|---|
| Faddoul Supermarket | faddoulsupermarket.com | DEAD — compromised/malware-injected | Every response (including a 404 REST probe) carries an injected `<script src="https://foreignabnormality.com/...">` tag — classic hacked-WordPress signature. Also has no WooCommerce Store API exposed. Do not scrape. See `known_blockers.md`. |
| Amizhdam Supermarket | amizhdamsupermarket.com | INCONCLUSIVE — curl 403 | 403 on curl_cffi chrome124 only; not re-probed with other TLS profiles or Playwright this pass. |
| Dukakeen | www.dukakeen.com | INCONCLUSIVE — curl 403 | 403 on curl_cffi chrome124 on the `/product-category/grocery/` path; not re-probed further this pass. Dukakeen is a known multi-country (BH/OM) online pharmacy+grocery brand — worth a dedicated pass if Oman also needs candidates. |
| Al Osra Online | www.alosraonline.com | INCONCLUSIVE — timeout | `curl_cffi` timed out after 20s with 0 bytes received on the homepage; not retried. Al Osra is a real, well-known Bahrain supermarket chain — worth a fresh probe attempt (retry once, then Playwright if it still fails). |
| Ramez Shopping | ramezshopping.com | NOT FINGERPRINTED | 27KB homepage, 200 OK, no obvious platform signature found in the quick check; not pursued further given `megamart_bh` already closed the gap for this pass. |
| Al Mufeed Trading | almufeedsa.com | REJECTED — wrong country | Appeared in a Bahrain-adjacent search; page text and `hreflang=ar-sa` confirm Saudi Arabia, not Bahrain. See Jordan/Lebanon inventories for the same false-positive. |

## Dead ends worth remembering

- **Bahrain's grocery-retail web ecosystem is strong** — beyond the already-onboarded `aljazira_bh`/`lulu_bh` and the newly-shipped `megamart_bh`, at least 3 more named chains (Al Osra, Ramez, Dukakeen) surfaced in a single marketplace-first search and were not fully probed this pass due to time budget. A follow-up pass should retry Al Osra (timeout, not a hard block) and re-probe Dukakeen/Amizhdam with `curl_cffi` chrome120/safari17_0 before writing them off — the mandatory re-probe rule (bare 403 ≠ WAF) was not fully exhausted for these two given `megamart_bh` already secured the country.
- **django-oscar is now a confirmed storefront platform in this repo's fingerprint set** (asset paths `static/oscar/js/...`) — worth adding to `platform_fingerprints.md` in a future pass; its category-listing-carries-price pattern (no PDP visit needed) is a very cheap win when it appears.
