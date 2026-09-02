# Palau

_Inventory written: 2026-08-04_

| Source name                       | URL                                                                                                  | COICOP divisions covered                                                                                                                                                                        | Source type           | Cadence          | Auth required? | Machine-readable? | Anti-bot risk | Wayback coverage | Per-SKU IDs?     | Notes                                                                                                                         |
| --------------------------------- | ---------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------- | ---------------- | -------------- | ----------------- | ------------- | ---------------- | ---------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| Palau CPI                         | https://www.palaugov.pw/executive-branch/ministries/finance/budgetandplanning/consumer-price-index-cpi/ | 01 food, 02 alcohol/tobacco, 03 clothing, 04 housing/utilities, 05 furnishings, 06 health, 07 transport, 08 communication, 09 recreation, 10 education, 11 restaurants/hotels, 13 miscellaneous | NSO CPI               | Quarterly        | No             | HTML/PDF          | Low           | Yes              | No               | Palau CPI page lists major COICOP-style groups; PDF notes quarterly price collection from retail outlets. ([palaugov.pw][24]) |
| Palau Public Utilities / PNCC     | https://www.ppuc.com/ ; https://www.pnccpalau.com/                                                   | 04 utilities, 08 telecom                                                                                                                                                                        | Utility/telco tariffs | Annual/quarterly | No             | HTML/PDF          | Low           | Likely           | Plan IDs partial | Narrow but useful.                                                                                                            |
| No broad online supermarket found | —                                                                                                    | SKU-level 01, 02, 03, 05, 06, 09, 13 gap                                                                                                                                                        | —                     | —                | —              | —                 | —             | —                | —                | CPI reports are main source.                                                                                                  |

## Wave (2026-09-01) -- sweep result

Targeted this pass because Palau sits at 2/5 food sources (0-food/1-food tier
already exhausted for kiribati/tuvalu/american_samoa). Marketplace-first
discovery found no seller directory for Palau (no Palau-specific delivery
marketplace exists). Direct/local-context checks on the physical stores named
in review/directory sites:

| Candidate | URL(s) tried | Result |
| --- | --- | --- |
| WCTC Shopping Center (Koror, "biggest department store in Palau") | wctc.net (200 but domain collision -- unrelated Wisconsin, USA ISP); wctcpalau.com, wctcplaza.com | NXDOMAIN / wrong site. No e-commerce domain found. |
| Payless Market Palau | facebook.com/p/Payless-Market-Palau-...; payless-market-palau.business.site (404); paylessmarketpw.com, paylessmarketpalau.com | NXDOMAIN / Facebook-only. |
| Elilai Budget Mart | evendo.com directory listing only | WebFetch of the evendo page confirms no external website/ordering link is published anywhere on the listing -- address+hours only. |
| Wilson's Store | evendo.com directory listing only | Same as above -- directory-only. |
| Neco Plaza | facebook.com/necoplazapalau/; neco.com.pw, necoplaza.com | NXDOMAIN / Facebook-only. |

**No new source shipped.** `surangel_pw` remains Palau's only real
supermarket-scale online catalog; `canoehouse_palau` is prepared-food, not
grocery. Do not re-run these exact searches without a new signal (a launched
storefront, a Facebook page that starts advertising online ordering/delivery).
Re-check in ~6 months.
