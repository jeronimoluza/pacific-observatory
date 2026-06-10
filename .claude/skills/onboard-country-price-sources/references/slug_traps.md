# Slug traps

Countries whose `src/configs/regions.yaml` slug doesn't match the obvious lowercase-of-name. Grep here when the user-supplied country input is ambiguous — picking the wrong slug breaks the loader silently (manifests dropped under unknown country directories).

A slug is a "trap" when `slug != name.lower().replace(' ', '_')` *and* the common-usage short name differs from the slug. Regenerable from `regions.yaml` + `countries.yaml`.

## Known traps

| Common name(s) | Canonical slug |
|---|---|
| Laos | `lao_pdr` |
| Taiwan | `taiwan_china` |
| Hong Kong | `hong_kong_sar_china` |
| Macau / Macao | `macao_sar_china` |
| North Korea / DPRK | `korea_dem_peoples_rep` |
| South Korea / ROK / Korea | `south_korea` |
| Brunei | `brunei_darussalam` |
| Papua New Guinea / PNG | `papua_new_guinea` |
| Federated States of Micronesia / FSM / Micronesia | `micronesia_fed_sts` |
| Timor-Leste / East Timor | `timor_leste` |

## When the user input is ambiguous

- "Korea" alone → confirm North vs South before scaffolding. The cost of picking wrong is an entire onboarding run under the wrong slug.
- "China" → usually mainland (`china`), but if the context is retail / pricing comparisons it might be Hong Kong or Macao SARs. Ask.
- "Samoa" → almost always Samoa (`samoa`), not American Samoa (`american_samoa`). Confirm if context suggests US territory.

## Adding to this file

When you onboard a country whose slug surprised you, add a row above. Also flag it to the user — if the slug is non-obvious, downstream queries / CLI invocations against that country will trip on it too.
