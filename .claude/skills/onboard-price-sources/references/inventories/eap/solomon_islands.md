# Solomon Islands

_Inventory written: 2026-08-04_

| Source name                                                 | URL                                                                                       | COICOP divisions covered                     | Source type           | Cadence          | Auth required? | Machine-readable? | Anti-bot risk | Wayback coverage | Per-SKU IDs?     | Notes                                                                      |
| ----------------------------------------------------------- | ----------------------------------------------------------------------------------------- | -------------------------------------------- | --------------------- | ---------------- | -------------- | ----------------- | ------------- | ---------------- | ---------------- | -------------------------------------------------------------------------- |
| Solomon Islands National Statistics Office CPI              | https://statistics.gov.sb/category/statistics/economic-statistics/consumer-price-index/   | 01–13 CPI groups                             | NSO CPI               | Monthly          | No             | PDF/HTML          | Low           | Yes              | No               | Official CPI bulletins available; 2025/2026 updates present. ([SINSO][27]) |
| Solomon Power / Solomon Telekom / fuel regulator candidates | https://solomonpower.com.sb/ ; https://www.telekom.com.sb/                                | 04 electricity/fuel, 08 telecom              | Utility/telco tariffs | Annual/irregular | No             | HTML/PDF          | Low           | Likely           | Plan IDs partial | Useful for tariffs.                                                        |
| No broad online supermarket found                           | —                                                                                         | SKU-level 01, 02, 03, 05, 06, 09, 11, 13 gap | —                     | —                | —              | —                 | —             | —                | —                | CPI/utility sources dominate.                                              |

## Wave (2026-09-01) -- sweep result

Targeted because Solomon Islands sits at 2/6 food sources. Note:
`hugsolomons_sb.yaml` (channel: `other`, already onboarded) actually carries
a majority-food catalog (68 of ~115 real SKUs are Food) but was deliberately
tagged `other` by a prior pass because the remaining categories (Body Care,
OTC Drugs, Clothes) don't let it cleanly fit any single retail channel enum
value -- left as-is, not reclassified this pass (not this agent's country
assignment to re-litigate a prior classification call, and it already exists
so it wouldn't move the food-source count either way).

New candidates checked:

| Candidate | URL(s) tried | Result |
| --- | --- | --- |
| Bulk Solomons (food importer/distributor, Ranadi Industrial Estate, Honiara) | bulksolomons.com.sb / www.bulksolomons.com.sb | **DEAD -- broken infrastructure, not a WAF.** HTTPS fails on every SNI/impersonation profile with `TLSV1_ALERT_INTERNAL_ERROR` (confirmed with curl_cffi, openssl s_client, and plain curl --tlsv1.2) -- a server-side TLS misconfiguration, not a bot block. Plain HTTP on the same host (74.208.236.168) returns a generic nginx catch-all 404 on every path tried (`/`, `/home`), meaning the vhost for this domain either isn't configured or the site has moved off this IP. evendo.com's Bulk Shop directory listing does not link to any of this. Site is effectively down/dead as of 2026-09-01, not scrapeable regardless of anti-bot posture. |
| Panatina Plaza supermarket, Wings Supermarket, Deli in the Plaza Supermarket | panatinaplaza.com, wingssupermarket.com.sb, deliintheplaza.com (guessed domains) | **NXDOMAIN on all three** -- no working domain found by direct guess. These read as Facebook-only businesses per search snippets (Deli in the Plaza has a Facebook page, not a website). |

**No new source shipped this wave.** Solomon Islands remains genuinely thin
for online grocery retail beyond the two already-onboarded Cabit storefronts.
Re-check bulksolomons.com.sb in a few months in case the TLS/hosting issue is
transient rather than permanent (it reads as more decommissioned than
mid-migration, but the evidence is not conclusive either way).
