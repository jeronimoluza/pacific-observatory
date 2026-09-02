# Nepal

_Inventory written: 2026-09-01_

Scope note: **food-and-beverage-focused seed** from the SAR agent-B depth pass (F&B retail only, division 01/02). No new source shipped this pass — recorded here so the next run does not repeat the same candidate checks. WebSearch budget was exhausted mid-pass (session-wide cap); everything below came from direct `curl_cffi` domain probing and Playwright renders.

Already onboarded before this pass: groceriesnepal_np, onlinesaathi, smartdoko, vhandar_np (all supermarket), shopitnepal_np (convenience), daraz_np (marketplace, keyword-walked for food), milanwholesale_np (wholesale, dry staples), epharmacy_np (pharmacy). Plus kalimati_market (official_avg fetcher — Kalimati wholesale fruit/veg market, already fills the "fresh produce reference price" gap at the official-average layer). Nepal already has good retailer-type breadth (supermarket + convenience + marketplace + wholesale); this pass specifically looked for **fresh-market** and **specialty-food** retailer_sku gaps and did not find a scrapeable one.

| Candidate | URL | Why not shipped |
|---|---|---|
| Foodmandu | https://foodmandu.com/ | Real, live restaurant food-delivery platform ("List your Restaurant") — wrong COICOP division (11 prepared food, not 01/02 retail). |
| Everest Organic | https://everestorganic.com.np/ | React/Vite SPA — turned out to be a vermicompost/soil-fertilizer agribusiness (earthworm farming, vermi-compost), not a food retailer despite the "Organic" name. |
| Muncha.com | https://muncha.com/ | Large reachable site, but a diaspora gift-and-money-transfer service ("Send Father's Day Gifts and Money to Nepal") — not investigated further for local grocery given the diaspora-pricing pattern seen elsewhere this wave (see Sri Lanka inventory). |
| Gyapu.com | https://gyapu.com/ | Domain parked / for sale (confirmed via Playwright render: "This domain is available for sale"). Unrelated to groceries. |
| Bhat-Bhateni | https://www.bhatbhateni.com/ | Nepal's largest supermarket chain — TLS cert expired on `curl_cffi`. Not investigated further this pass (also would be another supermarket-type source, deprioritized per the breadth-over-another-chain rule). Worth a re-check with `verify=False` in a future pass focused on supermarket depth specifically. |
| Sastodeal | https://sastodeal.com/ | General e-commerce marketplace — connection timed out (15s) on `curl_cffi chrome124`. Not re-probed with other impersonation profiles. |
| haatbazaar.com | https://haatbazaar.com/ | Resolves but serves a 114-byte response (redirect stub). Not investigated further. |
| Bhoos, khadya.com.np, dokan.com.np, namastebazaar.com.np, saguntagreen.com, kirana.com.np | various | Domain guesses (no WebSearch budget remaining to confirm real names/URLs) — none resolved. Not real findings, just ruled-out guesses; do not re-try these exact domains, but the underlying "Nepali quick-commerce app" and "specialty ghee/spice shop" categories are still open questions for a future pass with search budget available. |

## Next steps for a future pass

- Re-run domain discovery for Nepal with WebSearch available (this pass was search-budget-starved for Nepal specifically, having spent its share on Maldives/Sri Lanka first per the ranked worklist).
- Bhat-Bhateni's expired TLS cert is worth one `verify=False` + spam-signature check before writing off (per rule 14 — expired cert alone isn't dead, only expired-cert-plus-hacked-WordPress-signature is).
- Fresh-market and specialty-food channels remain open gaps for Nepal; Kalimati (official_avg) covers the reference-price layer but not a retailer_sku fresh-market source.
