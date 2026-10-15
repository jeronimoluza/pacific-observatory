# EAP country names for the `Country` column

The dashboard groups rows by matching the `Country` cell against a list of
exact strings (`WB_PIC_MEMBERS` in `src/text/plotting/policy_dashboards.py`).
Nothing normalizes spelling on the way in, so `Papua New Guinea` and `PNG`
render as two separate countries and split their counts, and a PIC spelled
the long way silently drops out of the `World Bank PICs only (12)` view.

Write the right-hand column verbatim. It is derived from
`src/configs/countries.yaml`, except for the four rows marked **override**,
where the workbook's own abbreviation is canonical and three of those four
are PIC members the view matches on.

Scope is every slug under `eap.subregions` in `src/configs/regions.yaml`.
If that file gains an economy, this table is stale — regenerate it rather
than guessing a spelling.

## East Asia (8)

| `regions.yaml` slug | Write in `Country` |
|---|---|
| `china` | `China` |
| `hong_kong_sar_china` | `Hong Kong SAR, China` |
| `japan` | `Japan` |
| `korea_dem_peoples_rep` | `Korea, Dem. People's Rep.` |
| `south_korea` | `Korea, Rep.` |
| `macao_sar_china` | `Macao SAR, China` |
| `mongolia` | `Mongolia` |
| `taiwan_china` | `Taiwan, China` |

## Pacific Islands (19)

| `regions.yaml` slug | Write in `Country` |
|---|---|
| `american_samoa` | `American Samoa` |
| `australia` | `Australia` |
| `fiji` | `Fiji` · PIC |
| `french_polynesia` | `French Polynesia` |
| `guam` | `Guam` |
| `kiribati` | `Kiribati` · PIC |
| `marshall_islands` | `RMI` **(override)** · PIC |
| `micronesia_fed_sts` | `FSM` **(override)** · PIC |
| `nauru` | `Nauru` · PIC |
| `new_caledonia` | `New Caledonia` |
| `new_zealand` | `New Zealand` |
| `northern_mariana_islands` | `Northern Mariana Islands` |
| `palau` | `Palau` · PIC |
| `papua_new_guinea` | `PNG` **(override)** · PIC |
| `samoa` | `Samoa` · PIC |
| `solomon_islands` | `Solomon Islands` · PIC |
| `tonga` | `Tonga` · PIC |
| `tuvalu` | `Tuvalu` · PIC |
| `vanuatu` | `Vanuatu` · PIC |

## Southeast Asia (11)

| `regions.yaml` slug | Write in `Country` |
|---|---|
| `brunei_darussalam` | `Brunei Darussalam` |
| `cambodia` | `Cambodia` |
| `indonesia` | `Indonesia` |
| `lao_pdr` | `Laos` **(override)** |
| `malaysia` | `Malaysia` |
| `myanmar` | `Myanmar` |
| `philippines` | `Philippines` |
| `singapore` | `Singapore` |
| `thailand` | `Thailand` |
| `timor_leste` | `Timor-Leste` |
| `vietnam` | `Vietnam` |

## The 12 World Bank PICs

These twelve strings must appear exactly as written or the
`World Bank PICs only (12)` view loses a member with no error:

- `Fiji`
- `Kiribati`
- `RMI`
- `FSM`
- `Nauru`
- `Palau`
- `PNG`
- `Samoa`
- `Solomon Islands`
- `Tonga`
- `Tuvalu`
- `Vanuatu`
