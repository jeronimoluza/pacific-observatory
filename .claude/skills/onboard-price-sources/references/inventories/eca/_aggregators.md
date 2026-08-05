# ECA multi-country sources

_Inventory written: 2026-08-04_

Cross-region aggregators surfaced during ECA country onboarding runs. When onboarding a new ECA country, check whether any of these already cover it before scaffolding country-specific equivalents.

| Source name | URL | COICOP divisions covered | Source type | Cadence | Auth required? | Machine-readable? | Anti-bot risk | Wayback coverage | Per-SKU IDs? | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Eurostat HICP | https://ec.europa.eu/eurostat/databrowser/view/prc_hicp_midx/ | 01-12 | NSO CPI division indexes | monthly | no | JSON-API | low | yes | no | Ukraine HICP-equivalent series carried via candidate-country reporting since 2023; gold benchmark for cross-ECA comparison. Same Eurostat endpoint covers all EU MS + candidates. |
| IMF CPI database | https://data.imf.org/cpi | 01-12 | NSO CPI division indexes | monthly | no | JSON-API | low | yes | no | All-items + COICOP subdivisions for every ECA country; SDMX endpoint; cross-region constant-method comparator. |
| World Bank ICP | https://databank.worldbank.org/source/icp-2021 | 01-12 | NSO CPI division indexes | irregular | no | XLS | low | yes | no | PPP benchmark — covers all ECA countries in 2017 and 2021 rounds; foundational for real-exchange-rate work. |
| Booking.com country pages | https://www.booking.com/country/{cc}.html | 11 | Hotel booking | daily | no | HTML | high | partial | yes | Per-property pricing with JSON-LD; same crawler template works across countries. |
| Numbeo | https://www.numbeo.com/cost-of-living/country_result.jsp?country={Country} | 01, 04, 07, 11 | Official food / commodity tracker | monthly | no | HTML-table | low | yes | no | Crowd-sourced cost-of-living; not authoritative but useful for triangulation across ECA. |
| EC Agri-food prices | https://agridata.ec.europa.eu/extensions/DataPortal/prices.html | 01 | Official food / commodity tracker | weekly | no | XLS | low | yes | no | EU agri-food price observatory; Ukraine grain/dairy included since 2022 association reporting. |
| UkrAgroConsult | https://ukragroconsult.com/en/grain-prices/ | 01 | Official food / commodity tracker | weekly | no | HTML-table | low | yes | no | FOB Black Sea wheat/corn/barley; covers UA + RU + KZ — fits ECA cross-country grain comparison. |
