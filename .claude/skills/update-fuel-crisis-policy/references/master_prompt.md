# Master prompt — Fuel Crisis Policy tracker update

This is the research brief for the `update-fuel-crisis-policy` skill.
It governs how the regional Excel workbooks are updated before
`po text build-policy-addons` regenerates the dashboard HTML addons.

Two design rules below are also enforced by the converter
(`src/text/plotting/policy_dashboards.py`), so even if a row slips,
the dashboard will normalize it:

- `eap` exposes a screenshot-friendly `World Bank PICs only (12)`
  country view: Fiji, Kiribati, RMI, FSM, Nauru, Palau, PNG, Samoa,
  Solomon Islands, Tonga, Tuvalu, Vanuatu.
- The deprecated label `Reduce demand` is auto-split into
  `Reduce demand - higher prices` and `Reduce demand - restricting
  quantities` based on text content. Reclassify in the workbook
  anyway — don't rely on the auto-split.

# Primary taxonomy — v6 Category + Subcategory

Starting with the v6 consolidated policy dataset, every Policies-sheet
row must carry **both** of these dashboard-rendered fields:

- `Category` — one of 6 closed-enum values
- `Subcategory` — one of 31 closed-enum values, constrained by Category

These are now the primary classification axis the dashboard renders
(bar color = Category; stacked segments = Subcategory; filter pair =
Category + cascading Subcategory). The legacy `Label` column is kept
in the workbook for audit/history but is **not rendered** by the new
dashboard.

The closed 6×31 enum (lowercase, canonical spelling):

| Category | Subcategories |
|---|---|
| `agriculture` | agricultural trade & export measures; domestic production & innovation; input subsidies & direct support; input supply, procurement & reserves; market regulation & price stabilization |
| `energy` | energy transition & efficiency; price & market interventions; subsidies & financial support; supply & infrastructure; trade & regulatory measures |
| `firm liquidity and financial support` | credit & liquidity instruments; direct grants & subsidies to firms; financial sector & external financing; msme-targeted support; regulatory & compliance relief; trade finance & export support |
| `fiscal measures` | financial stabilization and reserve management; fiscal consolidation; subsidies; tax and tariff measures |
| `regulatory and trade facilitation reforms` | emergency & coordination measures; fiscal & financial support; labor market & workforce measures; regulatory & business environment reforms; trade, logistics & connectivity |
| `social protection` | direct assistance & transfers; human development services; humanitarian & emergency response; market regulation & consumer protection; operational & logistics support; social insurance & protection |

The authoritative reference is the `Taxonomy` sheet inside each
regional workbook (formerly `Taxonomy_v6`; renamed 2026-06-04 when the
legacy v5 `Categories` sheet was retired). When in doubt, use that sheet
as the closed-enum source of truth.

Assignment rule: if a policy is sourced from the v6 consolidated file
(`data/text/policy_tracker/consolidated_policies/consolidated_policy_responses_v6.xlsx`),
copy the v6 row's `category` and `subcategory` verbatim (lowercased,
trimmed). For policies sourced elsewhere (existing workbook rows, new
research), pick the closest match from the closed enum above based on
the policy's dominant mechanism — never invent new values, never leave
blank.

# Regional workbooks

The current regional trackers live at
`data/text/policy_tracker/<region>.xlsx` for these region keys:

- `eap`
- `eca`
- `menaap`
- `sar`
- `ssa`
- `lac`

Important regional rule: Afghanistan and Pakistan are tracked under
MENAAP, not South Asia/SAR, to avoid duplication. Remove or exclude
Afghanistan and Pakistan from SAR workbooks and SAR dashboards unless
the user explicitly changes this rule.

# Objective

For each regional workbook, update the policy-response rows so that the
workbook reflects the best currently available evidence on national and
regional policy measures responding to the fuel/energy crisis.

The output should be an updated Excel workbook for each region,
preserving the workbook's existing schema as much as possible, while
ensuring that the dashboard-compatible policy fields are complete and
accurate.

At minimum, each valid policy row should support these dashboard fields:

- Country or economy
- Policy name
- Policy description
- **Category** (one of 6 closed-enum v6 values — required, dashboard-rendered)
- **Subcategory** (one of 31 closed-enum v6 values constrained by Category — required, dashboard-rendered)
- `Label` (legacy 8-value enum — kept for audit, not rendered)
- Active or proposed date
- Source name
- Source URL, where available
- Evaluation / verification status
- Reason or evidence note

Do not invent measures. Do not fill gaps speculatively. When evidence is
weak or unavailable, clearly flag the row as unverified, uncertain,
excluded, or needing follow-up.

# Legacy `Label` column — audit-only

The `Label` column below is retained on the Policies sheet for audit
and rollback, but the v6 dashboard does **not** render it. Populate
Category + Subcategory (see "Primary taxonomy" above) on every row;
keep `Label` accurate when it's already populated, but do not block
adding a new row if the closest Label match is ambiguous.

The closed Label enum (legacy; old label `Reduce demand` is deprecated
and should not remain):

- Communication
- General consumption smoothing
- Guaranteeing essential services
- Reduce demand - higher prices
- Reduce demand - restricting quantities
- Secure supply
- Support to business
- Support to households

# Core definitions

A valid policy row is a government, regulator, public utility,
state-owned enterprise, or official regional-body action that responds
to the fuel/energy crisis through one or more of the categories below.

## 1. General consumption smoothing

Use this label for policies that smooth or reduce fuel-price
pass-through to consumers or the economy generally, especially broad
fiscal or administered-price measures.

Examples include:

- Fuel tax cuts
- VAT, GST, or excise reductions
- Pump-price caps
- Price smoothing funds
- Subsidies to keep retail prices below market
- Anti-price-gouging enforcement
- Fiscal measures that directly reduce household or business fuel-price
  pass-through

## 2. Support to households

Use this label for direct household support or benefits primarily
targeted at household welfare.

Examples include:

- Cash transfers
- Transport vouchers
- LPG or kerosene support
- Electricity-bill support
- Welfare top-ups
- Low-income compensation

## 3. Support to business

Use this label for direct support to firms, producers, service
providers, or affected sectors.

Examples include:

- Fuel rebates for firms
- Support to transport operators, logistics firms, farmers, fishers,
  SMEs, utilities, airlines, or other affected sectors
- Credit guarantees or tax relief explicitly linked to the fuel/energy
  crisis

## 4. Guaranteeing essential services

Use this label for emergency measures intended primarily to keep core
services functioning.

Examples include:

- Emergency declarations
- Public transport continuity support
- Electricity-system emergency measures
- Backup generation procurement
- Support to hospitals, schools, food transport, ports, shipping,
  aviation, or other essential services

## 5. Reduce demand - higher prices

Use this label for policies that reduce fuel or energy demand primarily
by raising effective consumer or user prices, allowing larger price
pass-through, reducing price subsidies, raising administered fuel or
electricity prices, increasing charges, or moving regulated prices
closer to market levels.

Examples include:

- Fuel-price increases explicitly justified as necessary to conserve
  supply or preserve financial viability of fuel operations
- Subsidy phase-downs or subsidy reductions that intentionally raise
  effective prices
- Higher electricity or fuel tariffs linked to the fuel/energy crisis
- Price-adjustment mechanisms that increase domestic fuel prices to
  constrain demand, reduce fiscal costs, or maintain supply operations

Do not use this label for tax cuts, price caps, or subsidies that lower
prices. Those usually belong under `General consumption smoothing`,
`Support to households`, or `Support to business`.

## 6. Reduce demand - restricting quantities

Use this label for policies that reduce fuel or energy demand primarily
through quantity restrictions, non-price conservation requirements,
behavioral controls, rationing, or limits on use.

Examples include:

- Work-from-home orders
- Travel restrictions
- Government vehicle-use limits
- Fuel-purchase caps
- Odd-even vehicle rules
- Rationing
- Public-sector fuel conservation
- Air-conditioning limits
- Restrictions on operating hours or power consumption
- Public transport incentives used to reduce private fuel demand
- Biofuel, EV, or efficiency measures explicitly framed as immediate or
  crisis-related demand reduction
- Public energy-saving campaigns, if the campaign is primarily about
  changing consumption behavior rather than market communication

## 7. Secure supply

Use this label for policies that protect physical fuel or energy
availability, imports, reserves, storage, production, or logistics.

Examples include:

- Strategic reserve release or build-up
- Fuel import diversification
- Emergency procurement
- Export restrictions
- Refinery throughput orders
- Fuel stockholding changes
- Emergency cargoes
- Safe-passage diplomacy
- Anti-smuggling measures
- Supply-chain coordination

## 8. Communication

Use this label for official monitoring, coordination, public messaging,
and non-binding market-stabilization communication.

Examples include:

- Official monitoring task forces
- Public fuel-supply assurances
- Anti-hoarding advisories
- Crisis coordination committees
- Price-monitoring announcements
- Regional watch-phase participation
- Public briefings that are clearly part of the crisis response

Avoid counting purely analytical commentary, general long-term
energy-transition aspirations, or ordinary pre-existing policies unless
the source explicitly links them to the fuel/energy crisis response.

# Typology migration rules

When updating existing workbooks, reclassify all rows previously labeled
`Reduce demand`.

Use `Reduce demand - higher prices` when the direct mechanism is an
increase in effective price or a deliberate price pass-through intended
to moderate demand or preserve supply operations.

Use `Reduce demand - restricting quantities` when the direct mechanism
is a quota, rationing rule, driving restriction, travel restriction,
work-from-home order, conservation rule, air-conditioning limit,
operating-hour limit, or similar non-price restriction.

If a prior `Reduce demand` row is really just a public advisory
without a strong behavioral restriction, consider `Communication`
instead. If it is a subsidy or tax relief that lowers prices, it should
not remain in a demand-reduction category.

# Source hierarchy

Use the strongest available evidence. Prefer sources in this order:

1. Official legal instruments, gazettes, executive orders, regulations,
   ministerial decrees, parliamentary bills, regulator orders
2. Official government, ministry, regulator, central bank, utility, or
   state-owned enterprise releases
3. Reputable international trackers or institutions, especially IEA,
   OECD, IMF, World Bank, UN, regional development banks, and official
   regional bodies
4. Reputable local news and major international news wires
5. Local business press, sectoral press, and recognized civil-society
   sources
6. Government or official social-media posts, only when no better
   source is available or when the social-media account is the primary
   official channel
7. Unofficial social-media posts, blogs, or secondary summaries should
   only be used as leads, not as final proof

Broad regional summaries are leads, not final proof. Use them to
identify possible measures, then triangulate with country-specific
sources wherever possible.

# Search protocol

For each region, proceed systematically.

## Step 1: Establish the update window

Identify the workbook's current last-updated date from metadata,
filenames, notes, or the most recent policy row. Then search for new
developments from that date through the current run date.

If no update date is available, use a conservative window beginning from
the earliest known crisis-response period in the workbook, then focus
more heavily on recent results.

Document the update window in a notes/audit sheet.

## Step 2: Preserve and review existing rows

For every existing policy row:

- Check whether the policy remains active, has expired, was enacted, was
  withdrawn, or was superseded.
- Preserve valid rows unless there is clear evidence they are wrong or
  duplicative.
- Do not delete uncertain rows silently. Mark them as `Unverified`,
  `Needs follow-up`, `Superseded`, or `Excluded from dashboard`,
  depending on the workbook convention.
- Where a row is valid but too broad, split it into separate policy
  instruments if the workbook/dashboard logic counts policies
  individually.
- Where several rows are duplicative, consolidate only if they describe
  the same instrument and the same implementing authority. Keep separate
  rows for distinct instruments even if they belong to one package.
- Reclassify any row labeled `Reduce demand` using the updated
  two-part demand-reduction typology.

## Step 3: Search by country and policy instrument

For each country/economy in the region, search separately across these
policy-instrument types:

- fuel price cap
- fuel price increase
- administered fuel price adjustment
- fuel tax cut
- excise tax cut
- VAT or GST fuel relief
- fuel subsidy
- subsidy phase-down
- electricity tariff increase
- electricity subsidy
- LPG or kerosene subsidy
- transport subsidy
- public transport support
- fuel rationing
- fuel-purchase cap
- odd-even vehicle restrictions
- work from home
- official travel cuts
- government vehicle restrictions
- air-conditioning limits
- energy conservation campaign
- anti-hoarding
- anti-profiteering
- price gouging
- fuel smuggling enforcement
- fuel import diversification
- emergency fuel procurement
- strategic reserves
- oil reserve release
- minimum stockholding obligation
- export restriction
- refinery output order
- fuel quality relaxation
- fuel emergency declaration
- energy emergency declaration
- emergency response committee
- regulator order
- public utility fuel cost support
- state-owned fuel company action
- central bank foreign exchange support for fuel imports
- regional emergency coordination

Also search by likely implementing agencies:

- Ministry of Energy
- Ministry of Finance
- Ministry of Economy
- Ministry of Trade or Commerce
- Transport ministry
- Public works ministry
- Prime Minister, President, or Cabinet office
- Competition or consumer-protection regulator
- Energy regulator
- Utilities regulator
- Customs authority
- Tax authority
- Central bank
- State-owned oil, fuel, or gas companies
- Electricity utilities
- Port authorities
- Transport regulators
- Emergency management agencies
- Regional organizations

## Step 4: Use multilingual and local-language searches

For non-English jurisdictions, search in English and in the main
official/local language where feasible.

Use translated terms for: fuel, gasoline/petrol, diesel, LPG, kerosene,
energy crisis, fuel subsidy, fuel price, fuel price increase, fuel tax,
emergency, hoarding, rationing, strategic reserve, public transport,
electricity bill, price cap, excise, VAT/GST, decree, regulation,
gazette.

When using machine translation, record the source language if relevant
and avoid over-interpreting ambiguous terms.

## Step 5: Add new policy rows only when evidence is adequate

For a new row, require at least one credible source that identifies:

- the country/economy or regional body,
- the policy or action,
- the implementing authority,
- the approximate timing,
- and its link to the fuel/energy crisis.

For high-impact fiscal or legal measures, prefer at least two sources or
one official/legal source.

If a regional or news summary says a country is considering measures but
no specific measure is identified, include it only as a
communication/proposed/planning row and clearly state that details are
not yet available.

## Step 6: Categorize consistently

Assign exactly one (Category, Subcategory) pair from the closed v6 enum
to every row — this is what the dashboard renders. Optionally also fill
the legacy `Label` for audit continuity.

Use the direct recipient or dominant mechanism to pick the v6 pair:

- A fuel-price cap, fuel-tax reduction, VAT/GST relief, excise cut, or
  stabilization-fund drawdown that keeps retail fuel prices below market
  → Category `energy`, Subcategory `subsidies & financial support` (or
  `price & market interventions` for non-fiscal price administration).
- A subsidy phase-down, deregulation, or administered-price increase
  intended to reduce fiscal cost or curb demand → Category `energy`,
  Subcategory `price & market interventions`.
- A tax/excise change unrelated to fuel-specific retail prices (broad
  VAT or excise reform) → Category `fiscal measures`, Subcategory
  `tax and tariff measures`.
- A cash transfer, household LPG/kerosene subsidy, electricity-bill
  rebate, or low-income compensation → Category `social protection`,
  Subcategory `direct assistance & transfers`.
- A humanitarian response to displaced or crisis-affected households
  → Category `social protection`, Subcategory `humanitarian & emergency
  response`.
- A subsidy or rebate paid to transport operators, fishers, airlines,
  utilities, or SMEs → Category `firm liquidity and financial support`,
  Subcategory `direct grants & subsidies to firms` (or
  `msme-targeted support` if MSME-scoped).
- A credit line, working-capital loan, or central-bank liquidity window
  → Category `firm liquidity and financial support`, Subcategory
  `credit & liquidity instruments`.
- Emergency import procurement, strategic reserves, refinery output
  orders, anti-smuggling, supply diversification → Category `energy`,
  Subcategory `supply & infrastructure` (or `trade & regulatory
  measures` for trade-side actions).
- Government work-from-home orders, vehicle-use restrictions, fuel
  purchase caps, rationing, conservation orders, AC limits → Category
  `regulatory and trade facilitation reforms`, Subcategory
  `emergency & coordination measures`.
- Emergency declarations, crisis coordination committees, public
  monitoring task forces, anti-hoarding advisories → Category
  `regulatory and trade facilitation reforms`, Subcategory
  `emergency & coordination measures`.
- Export restrictions or import-licensing changes → Category
  `regulatory and trade facilitation reforms`, Subcategory
  `trade, logistics & connectivity`.
- Foreign-exchange support, reserve management, or financial
  stabilization for fuel imports → Category `fiscal measures`,
  Subcategory `financial stabilization and reserve management`.
- Input subsidies for farmers/fishers facing fuel-cost shocks
  → Category `agriculture`, Subcategory `input subsidies & direct
  support`.

If a row spans multiple plausible pairs, pick the dominant mechanism
and explain the choice in the reason/evidence note. Never leave
Category or Subcategory blank. Never invent values outside the closed
enum — if no pair fits, the row probably isn't dashboard-relevant.

## Step 7: Date/status convention

Use a concise status/date field compatible with the dashboard, such as:

- `Active Mar-26`
- `Active 15-Apr-26`
- `Proposed Apr-26`
- `Upcoming 11-May-26`
- `Expired May-26`
- `Superseded Apr-26`
- `Unverified Mar-26`

For enacted measures with implementation pending, use `Active` only if
the legal/administrative authority is already in force. Use `Upcoming`
if the measure has been approved but takes effect on a known future
date. Use `Proposed` if legislative, cabinet, budget, or regulatory
approval is still pending.

If the source gives only a month, use month-level text. Do not invent
exact dates.

## Step 8: Source URL and evidence note

Every new or updated row should include:

- Source name
- Source URL, where available
- Evaluation status
- Reason/evidence note

The reason/evidence note should briefly state why the row is included
and what source confirms it. It should also flag caveats, such as:

- `Official source confirms announcement but implementation details not
  yet published.`
- `Local reporting only; no gazette found.`
- `Regional-summary row; country-specific details not available.`
- `Potential overlap with existing tax-relief row; retained separately
  because source describes distinct instrument.`
- `Excluded from dashboard because this is a coverage note, not a
  policy measure.`

# Regional coverage rules

## EAP

The country universe is every slug listed under `eap.subregions` in
`src/configs/regions.yaml` — 38 economies across `east_asia`,
`pacific_islands` and `southeast_asia`. Enumerate that file at the start of
the pass and work the whole list. Do not improvise a country list, and do
not infer scope from which countries already have rows: an economy missing
from the workbook is a gap to fill, not evidence that it is out of scope.

Write the `Country` cell using the spelling in
`references/country_names.md`. The dashboard matches country names by exact
string, so a spelling that drifts drops the row out of its country group
without any error.

An economy you searched and found no verified measure for must still be
named in the audit note, so its absence reads as covered rather than
skipped. This matters most for Guam, American Samoa, Northern Mariana
Islands, French Polynesia and New Caledonia, where the operative measures
are often US or French federal programmes rather than local ones.

Preserve any existing workbook country-group logic, such as Pacific-only,
East Asia-only, high-income, and low/middle-income views, if present.

The converter exposes the EAP `World Bank PICs only (12)` view
automatically when those 12 countries appear in the workbook.

## SAR

Track South Asia, but exclude Afghanistan and Pakistan if they are
already tracked in MENAAP. The SAR dashboard should not duplicate those
two countries.

Typical SAR countries after exclusion:

- Bangladesh
- Bhutan
- India
- Maldives
- Nepal
- Sri Lanka
- plus any other SAR workbook countries except Afghanistan and Pakistan,
  unless instructed otherwise

## MENAAP

Track Middle East, North Africa, Afghanistan, and Pakistan, according to
the workbook's existing country list. Afghanistan and Pakistan belong
here for this project's current division of labor.

## ECA

Track Europe and Central Asia according to the workbook's existing
country list. Be careful to distinguish real policy measures from
coverage-audit rows, source-gap rows, or statements that no verified
current discretionary fuel relief was found.

Rows that merely say `no verified current discretionary fuel relief
found` are auto-excluded from the dashboard by the converter; keep them
in the workbook as audit notes if useful.

## SSA

Track Sub-Saharan Africa according to the workbook's existing country
list. Include fuel price stabilization, subsidies, tax changes,
rationing, utility support, import/supply measures, and emergency
declarations where verified.

## LAC

Track Latin America and the Caribbean according to the workbook's
existing country list. Include national measures and material
subnational measures only if the workbook already tracks subnational
policy responses or if the measure is large enough to be relevant to
national policy monitoring.

# Workbook handling

Open each workbook and inspect the available sheets. Preserve existing
formatting and column structure where possible.

All six workbooks share a unified sheet layout:

- `Policies` — the policy rows (this is what the converter reads).
  Required dashboard-rendered columns: `Country`, `Policy`,
  `Policy Description`, `Category`, `Subcategory`. Legacy `Label`
  column is retained for audit but not rendered.
- `Taxonomy` — closed-enum reference for the (Category, Subcategory)
  pairs the dashboard renders. Treat as read-only. (Renamed from
  `Taxonomy_v6` on 2026-06-04; the legacy v5 `Categories` sheet was
  dropped at the same time.)
- `Update_Audit` — update memo / freeform notes.

If a workbook has dashboard-compatible columns, fill them directly. If
the workbook has a broader schema, preserve its schema and fill the
closest equivalents — the converter tolerates a wide range of alias
column names.

When adding rows:

- Keep country names consistent with existing workbook spelling.
- Keep policy labels consistent with the approved dashboard labels.
- Use stable, human-readable policy titles.
- Put detailed explanatory text in the policy description, not the
  title.
- Do not over-compress distinct instruments into one row merely because
  they were announced in one package.
- Do not split one instrument into multiple rows unless there are
  legally or operationally distinct components.

When revising rows:

- Update descriptions if new details improve accuracy.
- Update status/date if proposed measures became active, upcoming,
  expired, or superseded.
- Add or improve URLs.
- Add caveats where evidence remains weak.
- Avoid deleting old information unless clearly wrong; mark
  superseded/excluded instead.
- Replace deprecated `Reduce demand` labels with one of the two new
  demand-reduction labels.

# Evidence standards

Use these evaluation labels unless the workbook has its own required
labels:

- `Correct` — sufficiently verified and suitable for dashboard
  inclusion
- `Updated` — existing row revised based on new evidence
- `New` — newly added verified row
- `Proposed` — publicly announced or formally under consideration, but
  not yet implemented
- `Upcoming` — approved or formally announced with a future effective
  date
- `Expired` — measure has ended
- `Superseded` — replaced by a newer policy
- `Unverified` — plausible but evidence is insufficient
- `Excluded` — not a policy-response row or outside scope
- `Needs follow-up` — potentially important but unresolved

A row should not be marked `Correct` unless the evidence supports the
policy's existence, timing, and country attribution.

# Periodic update checklist

For each workbook:

1. Identify workbook region, sheet structure, and last update date.
2. Search for new policies since the last update.
3. Re-check high-salience existing policies for status changes.
4. Search official sources by country and implementing agency.
5. Search reputable international trackers.
6. Search local and international news.
7. Search social media only as supplemental evidence.
8. Add new rows with sources and caveats.
9. Update existing rows where details/status changed.
10. Reclassify all deprecated `Reduce demand` rows.
11. Mark expired, superseded, unverified, or excluded rows clearly.
12. Remove Afghanistan and Pakistan from SAR if present.
13. Confirm all dashboard-required fields are populated for valid rows.
14. Confirm labels use the approved category names.
15. Confirm no duplicate rows describe the same instrument.
16. For EAP, confirm the `World Bank PICs only (12)` view contains
    exactly 12 members. Fewer means a country name drifted from
    `references/country_names.md` — fix the spelling, not the view.
17. Confirm every Policies row has a non-blank (Category, Subcategory)
    pair in the closed v6 enum (see `Taxonomy` sheet).
18. Add an audit note summarizing the update window, searches performed,
    major additions, unresolved uncertainties, and excluded candidates.

# Suggested search queries

Use combinations of the following patterns, substituting country names,
local language terms, agency names, and dates.

## General

- `[country] fuel crisis 2026 government response`
- `[country] energy crisis 2026 fuel prices government`
- `[country] diesel petrol subsidy April 2026`
- `[country] fuel tax cut 2026`
- `[country] fuel price cap 2026`
- `[country] fuel price increase May 2026`
- `[country] administered fuel price adjustment 2026`
- `[country] energy emergency 2026 fuel`
- `[country] fuel rationing 2026`
- `[country] strategic fuel reserve 2026`
- `[country] fuel imports emergency procurement 2026`
- `[country] anti hoarding fuel 2026`
- `[country] fuel smuggling enforcement 2026`
- `[country] public sector work from home fuel saving 2026`
- `[country] transport subsidy fuel 2026`
- `[country] electricity subsidy fuel cost 2026`
- `[country] electricity tariff fuel cost 2026`

## Official-source targeted

- `site:gov [country] fuel price 2026`
- `site:gov [country] energy crisis 2026`
- `site:gov [country] diesel subsidy 2026`
- `site:gov [country] excise fuel 2026`
- `site:gov [country] gazette fuel 2026`
- `site:gov [country] emergency energy decree 2026`
- `site:gov [country] petroleum regulation 2026`
- `site:centralbank.* [country] fuel imports foreign exchange 2026`
- `site:energy.* [country] fuel supply 2026`
- `site:finance.* [country] fuel tax 2026`

## International trackers

- `IEA 2026 energy crisis policy response tracker [country]`
- `IMF [country] fuel subsidy 2026`
- `World Bank [country] fuel subsidy 2026`
- `OECD [country] energy crisis measures 2026`
- `Global Trade Alert [country] fuel 2026`
- `UN [country] fuel crisis 2026`

## Local implementation agencies

- `[country] competition commission fuel prices April 2026`
- `[country] utilities regulator fuel cost electricity April 2026`
- `[country] petroleum authority fuel supply April 2026`
- `[country] national oil company fuel imports April 2026`
- `[country] transport ministry fuel subsidy April 2026`
- `[country] customs fuel duty April 2026`
- `[country] tax authority fuel excise April 2026`
- `[country] state fuel company price adjustment May 2026`

# Update memo

After each region's update, produce a concise memo with:

1. Workbook name
2. Update window
3. Number of rows added
4. Number of rows revised
5. Number of rows reclassified under the updated demand-reduction
   typology
6. Number of rows marked expired/superseded/excluded
7. Countries with material new activity
8. Countries searched where no new verified policy was found
9. Unresolved uncertainties and follow-up items
10. Any changes that may affect the HTML dashboard generation

Every material claim should be traceable to a workbook row and source.

# Quality-control rules

Before finalizing:

- Check that all source URLs open or are otherwise documented.
- Check that each policy row is assigned to the correct country.
- Check that **every row has both `Category` and `Subcategory` populated**
  and that the pair is in the closed `Taxonomy` enum.
- Check that no row keeps the deprecated label `Reduce demand` in the
  legacy `Label` column (where `Label` is populated at all).
- Check that `Reduce demand - higher prices` is used only for
  price-increase or effective-price-increase mechanisms.
- Check that `Reduce demand - restricting quantities` is used for
  rationing, caps, vehicle restrictions, work-from-home rules, travel
  cuts, conservation orders, and other non-price restrictions.
- Check that Afghanistan and Pakistan are not included in SAR.
- Check that EAP's `World Bank PICs only (12)` view contains exactly
  12 members.
- Check that dashboard-relevant rows are not merely no-policy-found
  audit rows.
- Check that long policy descriptions are concise but specific.
- Check that exact dates are not invented.
- Check that upcoming measures with approved future effective dates use
  `Upcoming` or another clearly equivalent status convention.
- Check that regional-summary rows are clearly marked as
  regional-summary rows.
- Check that proposed measures are not misclassified as active.
- Check that expired measures remain historically accurate if retained.
- Confirm `poetry run po text build-policy-addons --region <r>` runs
  cleanly against the updated workbook.

# Style

Be conservative, precise, and evidence-driven. Prefer `not found` or
`uncertain` over speculation. Preserve useful uncertainty in the
workbook rather than hiding it. The goal is not to maximize the number
of policies; the goal is to maintain a reliable, auditable tracker and
a dashboard that can be updated periodically without schema drift.
