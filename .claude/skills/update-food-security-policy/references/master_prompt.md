# Master prompt — Food Security Policy tracker update

This is the research brief for the `update-food-security-policy` skill.
It governs how the regional Excel workbooks under
`data/text/policy_tracker/food_security/` are updated before
`po text build-policy-addons --tracker food` regenerates the dashboard
HTML addons.

Two design rules below are also enforced by the converter
(`src/text/plotting/policy_dashboards.py`), so even if a row slips, the
dashboard will normalize it:

- `eap` exposes a screenshot-friendly `World Bank PICs only (12)`
  country view: Fiji, Kiribati, RMI, FSM, Nauru, Palau, PNG, Samoa,
  Solomon Islands, Tonga, Tuvalu, Vanuatu.
- `sar` auto-excludes Afghanistan and Pakistan (tracked under MENAAP).

# Primary taxonomy — v6 Category + Subcategory (UNCHANGED)

Every Policies-sheet row must carry **both** of these
dashboard-rendered fields:

- `Category` — one of 6 closed-enum values
- `Subcategory` — one of 31 closed-enum values, constrained by Category

This is the **same enum the fuel tracker uses**, deliberately reused
without modification. Do not extend it, do not add food-specific
values, do not edit the `Taxonomy` sheet.

| Category | Subcategories |
|---|---|
| `agriculture` | agricultural trade & export measures; domestic production & innovation; input subsidies & direct support; input supply, procurement & reserves; market regulation & price stabilization |
| `energy` | energy transition & efficiency; price & market interventions; subsidies & financial support; supply & infrastructure; trade & regulatory measures |
| `firm liquidity and financial support` | credit & liquidity instruments; direct grants & subsidies to firms; financial sector & external financing; msme-targeted support; regulatory & compliance relief; trade finance & export support |
| `fiscal measures` | financial stabilization and reserve management; fiscal consolidation; subsidies; tax and tariff measures |
| `regulatory and trade facilitation reforms` | emergency & coordination measures; fiscal & financial support; labor market & workforce measures; regulatory & business environment reforms; trade, logistics & connectivity |
| `social protection` | direct assistance & transfers; human development services; humanitarian & emergency response; market regulation & consumer protection; operational & logistics support; social insurance & protection |

The authoritative reference is the `Taxonomy` sheet inside each regional
workbook. When in doubt, use that sheet as the closed-enum source of
truth.

For food security, `agriculture` and `social protection` will carry most
rows, with `regulatory and trade facilitation reforms` for export bans
and emergency declarations. `energy` still appears where fuel or
fertilizer-energy costs are the operative mechanism.

# Regional workbooks

`data/text/policy_tracker/food_security/<region>.xlsx` for region keys
`eap`, `eca`, `menaap`, `sar`, `ssa`, `lac`.

**Do not open or write `data/text/policy_tracker/<region>.xlsx`** — that
is the fuel tracker.

Important regional rule: Afghanistan and Pakistan are tracked under
MENAAP, not SAR, to avoid duplication.

# Objective

For each regional workbook, update the policy-response rows so the
workbook reflects the best currently available evidence on national and
regional policy measures responding to **food-security and food-price
stress**.

At minimum, each valid policy row should support these dashboard fields:

- Country or economy
- Policy name
- Policy description
- **Category** (one of 6 closed-enum v6 values — required, rendered)
- **Subcategory** (one of 31 closed-enum v6 values — required, rendered)
- `Label` (legacy enum — kept for audit, not rendered)
- Active or proposed date
- Source name
- Source URL, where available
- Evaluation / verification status
- Reason or evidence note — **including the shock that triggered it**

Do not invent measures. Do not fill gaps speculatively. When evidence is
weak, flag the row as unverified, uncertain, excluded, or needing
follow-up.

# The shock-trigger rule (read this twice)

Food-security crises are triggered by things that are not themselves
policies: drought, heatwaves, floods, cyclones, pest outbreaks,
fertilizer price spikes, export bans by trading partners, currency
depreciation raising import costs.

**The tracked object is always the government response.** The shock goes
in the `Reason` column as the evidence link that makes the row
crisis-related rather than routine.

| Not a row | A row |
|---|---|
| "Severe drought in northern provinces" | "Drought emergency declared; USD 40m relief fund for affected farmers" |
| "Global fertilizer prices up 60%" | "Fertilizer import subsidy raised to 50% of landed cost for smallholders" |
| "Rice prices rose 30% y/y" | "Retail price ceiling imposed on milled rice" |
| "Cyclone destroyed 40% of the taro crop" | "Emergency seed and planting-material distribution to affected households" |
| "FAO warns of IPC Phase 4 risk" | "National food security emergency declared; strategic grain reserve released" |

A row whose only content is the hazard is an **audit note**, not a
dashboard row — mark it `Excluded` with an explanatory `Reason`.

# Core definitions — policy families

Use these families to structure the search. They map to the v6 enum in
"Categorize consistently" below.

## 1. Consumer food price measures

Measures that lower or stabilize the retail price of food for
consumers.

- Retail price ceilings / maximum prices on staples
- VAT / GST / sales-tax exemption or reduction on food
- Import tariff suspension or reduction on grain, cooking oil, sugar,
  pulses, dairy, fertilizer
- Consumer food subsidies, subsidized bread / rice / flour programs
- Anti-price-gouging and anti-hoarding enforcement on food
- Price-monitoring and margin regulation for food retail

## 2. Household food assistance and social protection

Direct support to households targeted at food access.

- Food vouchers, food stamps, in-kind food rations
- Cash transfers explicitly justified by food prices or food insecurity
- School feeding programs (new, expanded, or extended)
- Targeted nutrition programs (maternal, child, acute malnutrition)
- Humanitarian food distribution to displaced or disaster-affected
  households
- Public food distribution system expansion

## 3. Producer and input support

Support to farmers, fishers, and livestock keepers.

- Fertilizer subsidies, vouchers, or bulk state procurement
- Seed and planting-material distribution, especially post-disaster
- Feed subsidies, livestock destocking or restocking programs
- Irrigation support, emergency water for agriculture
- Agricultural credit lines, debt moratoria, crop insurance payouts
- Fuel or electricity rebates specifically for irrigation, fishing
  vessels, or agro-processing
- Minimum support prices / guaranteed procurement prices for producers

## 4. Trade measures

Border actions altering food or input availability.

- Export bans, export quotas, export licensing, export taxes on food
- Import liberalization, tariff-rate-quota expansion, import licensing
  fast-tracking
- Phytosanitary or standards flexibility to speed food imports
- State-to-state food supply agreements, bilateral grain deals
- Anti-smuggling enforcement on food staples

## 5. Reserves, procurement and logistics

Physical availability of food.

- Strategic grain / food reserve release or build-up
- Emergency state procurement or import tenders
- Buffer-stock operations, open-market sales from reserves
- Storage capacity investment, post-harvest loss reduction programs
- Port, shipping, cold-chain, or inland-transport prioritization for
  food cargo
- Fuel allocation prioritized for food transport

## 6. Reduce consumption - higher prices

Policies that reduce food or input demand primarily by **raising
effective prices**: subsidy phase-downs, removal of price ceilings,
deregulation of administered food prices, raising procurement or ration
prices.

Do not use this for tax cuts, caps, or subsidies that lower prices.

## 7. Reduce consumption - restricting quantities

Policies that ration or restrict **quantities** rather than price:
purchase limits per household, ration-card quantity cuts, restrictions
on food exports by individuals, limits on grain used for biofuel or
animal feed, milling-extraction-rate mandates, food-waste mandates.

## 8. Climate and disaster response for agriculture

Measures responding to a weather or climate shock through the
agricultural or food system.

- Drought / flood / cyclone emergency declarations naming agriculture or
  food security
- Disaster relief funds for crop or livestock losses
- Emergency water allocation, water-use restrictions for irrigation
- Heat-related livestock protection measures
- Pest and disease outbreak control (locusts, armyworm, ASF, avian flu)
- Climate-resilient seed or practice programs framed as immediate crisis
  response

## 9. Coordination, monitoring and communication

- National food security task forces, emergency committees
- Official food price monitoring systems, early warning systems
- IPC / Cadre Harmonisé analyses commissioned or endorsed by government
- Public assurances on food supply, anti-hoarding advisories
- Regional food security coordination (ASEAN+3 APTERR, PIF, ECOWAS,
  SADC, GCC)

Avoid counting analytical commentary, long-horizon agricultural
development strategy, or ordinary pre-existing programs unless the
source explicitly links them to the current food-security crisis
response.

# Source hierarchy

Use the strongest available evidence:

1. Official legal instruments — gazettes, executive orders, ministerial
   decrees, regulations, parliamentary bills, regulator orders
2. Official government, ministry of agriculture/food/trade, regulator,
   central bank, marketing board, or state food-agency releases
3. Reputable international institutions and trackers — **FAO, WFP, IFPRI
   (Food and Fertilizer Export Restrictions Tracker), IPC/Cadre
   Harmonisé, FEWS NET, World Bank Food Security Update, IMF, UN OCHA,
   AMIS, regional development banks**
4. Reputable local news and major international wires
5. Local business press, agricultural sector press, recognized
   civil-society sources
6. Official social-media accounts, only when no better source exists
7. Unofficial social posts / blogs — leads only, never final proof

The World Bank **Food Security Update** and the IFPRI **Food and
Fertilizer Export Restrictions Tracker** are unusually high-yield
starting points for this tracker; treat them as lead generators, then
triangulate to a country-specific official source.

Broad regional summaries are leads, not final proof.

# Search protocol

## Step 1: Establish the update window

Identify the workbook's last-updated date from the `Update_Audit` sheet,
file metadata, or the most recent policy row. Search for developments
from that date to the current run date. For a fresh/empty workbook, use
a conservative window covering the last 24 months, weighted to recent
months.

Document the update window in `Update_Audit`.

## Step 2: Preserve and review existing rows

- Check whether the policy remains active, expired, was enacted,
  withdrawn, or superseded. Export bans in particular are frequently
  time-limited and quietly lapse — always re-verify status.
- Preserve valid rows unless clearly wrong or duplicative.
- Do not delete uncertain rows silently. Mark `Unverified`,
  `Needs follow-up`, `Superseded`, or `Excluded`.
- Split overly broad rows into distinct instruments; consolidate only
  when the same instrument and same implementing authority.

## Step 3: Search by country and policy instrument

For each country/economy in the region, search separately across:

**Prices and consumers**
- food price ceiling / maximum price staple food
- rice price control
- bread price subsidy
- cooking oil price cap
- VAT exemption food
- import tariff suspension food
- food price gouging enforcement
- food price monitoring

**Household assistance**
- food voucher program
- food ration distribution
- cash transfer food insecurity
- school feeding program expansion
- emergency food assistance
- public distribution system

**Producers and inputs**
- fertilizer subsidy
- fertilizer import
- seed distribution emergency
- livestock feed subsidy
- destocking program
- irrigation emergency funding
- agricultural credit moratorium
- crop insurance payout
- minimum support price

**Trade**
- rice export ban
- wheat export restriction
- sugar export quota
- food export licensing
- import liberalization grain
- phytosanitary waiver food import

**Reserves and logistics**
- strategic grain reserve release
- buffer stock open market sale
- emergency food import tender
- national food reserve procurement
- food transport priority

**Climate and disaster**
- drought emergency declaration agriculture
- flood damage crop compensation
- cyclone agriculture recovery
- heatwave livestock losses government
- locust control program
- armyworm outbreak response
- El Nino / La Nina food security response
- water restriction irrigation

**Coordination**
- national food security task force
- food security emergency declaration
- IPC analysis government response
- anti-hoarding food advisory

Also search by likely implementing agencies:

- Ministry of Agriculture / Agriculture and Livestock / Primary
  Industries
- Ministry of Food / Food Security
- Ministry of Fisheries
- Ministry of Trade or Commerce
- Ministry of Finance
- Ministry of Social Welfare / Social Development
- Prime Minister, President, or Cabinet office
- National Disaster Management Agency / Office
- Food / grain marketing boards, state trading enterprises
- Competition or consumer-protection regulator
- Customs authority
- Meteorological service (for shock attribution)
- Regional bodies: ASEAN Secretariat / APTERR, Pacific Islands Forum,
  SPC, ECOWAS, SADC, IGAD, CARICOM, GCC

## Step 4: Use multilingual and local-language searches

For non-English jurisdictions, search in English and the main
official/local language.

Translate terms for: food, rice, wheat, maize, bread, cooking oil,
sugar, fertilizer, seed, livestock, fisheries, harvest, drought, flood,
cyclone, heatwave, famine, food price, food security, export ban, price
ceiling, subsidy, ration, food aid, emergency, decree, gazette.

Record the source language where relevant; avoid over-interpreting
ambiguous terms.

## Step 5: Add new policy rows only when evidence is adequate

A new row requires at least one credible source identifying:

- the country/economy or regional body,
- the policy or action,
- the implementing authority,
- the approximate timing,
- **and its link to food security or food prices** (this is where the
  shock trigger is documented).

For high-impact fiscal, trade, or legal measures (export bans, tariff
suspensions, large transfer programs), prefer two sources or one
official/legal source.

If a summary says a country is considering measures but names no
specific measure, include it only as a coordination/proposed row and say
so explicitly.

## Step 6: Categorize consistently

Assign exactly one (Category, Subcategory) pair from the closed v6 enum:

- Retail food price ceiling, food VAT/tariff exemption, consumer food
  subsidy → `agriculture` / `market regulation & price stabilization`
  (use `fiscal measures` / `tax and tariff measures` when the instrument
  is a broad tax change rather than a food-market intervention).
- Food vouchers, food rations, food-justified cash transfers, school
  feeding → `social protection` / `direct assistance & transfers`.
- Emergency food distribution to disaster-affected or displaced
  households → `social protection` / `humanitarian & emergency response`.
- Nutrition programs, maternal/child feeding →
  `social protection` / `human development services`.
- Anti-hoarding / anti-price-gouging enforcement on food →
  `social protection` / `market regulation & consumer protection`.
- Fertilizer subsidy, seed distribution, feed subsidy, irrigation
  support, destocking → `agriculture` / `input subsidies & direct support`.
- State fertilizer/seed procurement, input stockpiles →
  `agriculture` / `input supply, procurement & reserves`.
- Strategic grain reserve release, buffer stock, state food procurement
  → `agriculture` / `input supply, procurement & reserves`.
- Minimum support prices, guaranteed procurement prices, open-market
  sales → `agriculture` / `market regulation & price stabilization`.
- Export bans, export quotas, import tariff-rate quotas, food import
  liberalization → `agriculture` / `agricultural trade & export measures`.
- Non-food-specific trade logistics, port prioritization, corridor
  agreements → `regulatory and trade facilitation reforms` /
  `trade, logistics & connectivity`.
- Climate-resilient seed programs, productivity/yield programs,
  post-harvest loss reduction → `agriculture` /
  `domestic production & innovation`.
- Agricultural credit lines, debt moratoria, crop insurance payouts to
  farmers → `firm liquidity and financial support` /
  `credit & liquidity instruments`.
- Grants or subsidies to agro-processors, millers, fishers, food
  retailers → `firm liquidity and financial support` /
  `direct grants & subsidies to firms` (or `msme-targeted support` if
  MSME-scoped).
- Drought/flood/cyclone emergency declarations, food security task
  forces, purchase limits, rationing rules, water-use restrictions →
  `regulatory and trade facilitation reforms` /
  `emergency & coordination measures`.
- Foreign-exchange allocation or reserve management for food imports →
  `fiscal measures` / `financial stabilization and reserve management`.
- Fuel or electricity subsidies for irrigation, fishing fleets, or
  agro-processing → `energy` / `subsidies & financial support`.

If a row spans multiple plausible pairs, pick the dominant mechanism and
explain in `Reason`. Never leave Category or Subcategory blank. Never
invent values outside the closed enum — if no pair fits, the row
probably isn't dashboard-relevant.

## Step 7: Date/status convention

Use concise status/date text compatible with the dashboard:

- `Active Mar-26`
- `Active 15-Apr-26`
- `Proposed Apr-26`
- `Upcoming 11-May-26`
- `Expired May-26`
- `Superseded Apr-26`
- `Unverified Mar-26`

`Active` only if the legal/administrative authority is already in force.
`Upcoming` if approved with a known future effective date. `Proposed` if
approval is still pending.

Export bans and price ceilings very often carry an explicit expiry —
capture it. If the source gives only a month, use month-level text. Do
not invent exact dates.

## Step 8: Source URL and evidence note

Every new or updated row needs Source name, Source URL, Evaluation
status, and a `Reason` note. The `Reason` should state why the row is
included, what source confirms it, **and what shock it responds to**.
Flag caveats, e.g.:

- `Responds to 2025-26 El Nino drought; official gazette confirms the
  emergency declaration but relief-fund disbursement is unverified.`
- `IFPRI tracker lists the export ban; national gazette not located.`
- `Local reporting only; no official source found.`
- `Excluded from dashboard because this is a hazard description, not a
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

Pacific island food security is dominated by **cyclone and drought crop
damage, import dependence, and shipping/freight disruption** — search those
channels explicitly for the PICs, and check SPC and Pacific Islands Forum
outputs.

All 12 World Bank PICs must appear, so the `World Bank PICs only (12)` view
populates with exactly 12 members.

## SAR

South Asia excluding Afghanistan and Pakistan (tracked in MENAAP).
Typically: Bangladesh, Bhutan, India, Maldives, Nepal, Sri Lanka. India's
rice and wheat export policy and public distribution system are
high-salience; Sri Lanka's fertilizer policy history is directly
relevant.

## MENAAP

Middle East, North Africa, Afghanistan, and Pakistan. Wheat import
dependence, bread subsidy programs, and strategic reserve policy are the
dominant channels.

## ECA

Europe and Central Asia. Watch grain export policy, food price caps in
Central Asia, and the Black Sea grain trade. Distinguish real measures
from coverage-audit rows.

## SSA

Sub-Saharan Africa. Fertilizer subsidy programs, maize export/import
restrictions, strategic grain reserves, drought and flood emergency
responses, and pest outbreaks (fall armyworm, locusts) are the dominant
channels. IPC / Cadre Harmonisé and FEWS NET are essential.

## LAC

Latin America and the Caribbean. Food price controls, fertilizer import
dependence, drought in the Dry Corridor and Southern Cone, and hurricane
crop damage in the Caribbean are the dominant channels. Include material
subnational measures only if the workbook already tracks them.

# Workbook handling

Preserve existing formatting and column structure. Sheet layout:

- `Policies` — the policy rows (what the converter reads). Required
  rendered columns: `Country`, `Policy`, `Policy Description`,
  `Category`, `Subcategory`.
- `Taxonomy` — closed-enum reference. **Read-only.**
- `Update_Audit` — update memo / freeform notes.

When adding rows:

- Keep country names consistent with existing workbook spelling.
- Use stable, human-readable policy titles; detail goes in the
  description, not the title.
- Do not over-compress distinct instruments into one row merely because
  they were announced together.
- Do not split one instrument into multiple rows unless legally or
  operationally distinct.

When revising rows:

- Update descriptions and status/date as evidence improves.
- Add or improve URLs; add caveats where evidence is weak.
- Mark superseded/excluded rather than deleting.

# Evidence standards

- `Correct` — sufficiently verified, suitable for dashboard inclusion
- `Updated` — existing row revised on new evidence
- `New` — newly added verified row
- `Proposed` — announced or formally under consideration, not implemented
- `Upcoming` — approved with a future effective date
- `Expired` — measure has ended
- `Superseded` — replaced by a newer policy
- `Unverified` — plausible but evidence insufficient
- `Excluded` — not a policy-response row or outside scope
- `Needs follow-up` — potentially important but unresolved

A row is not `Correct` unless the evidence supports the policy's
existence, timing, and country attribution.

# Periodic update checklist

1. Identify region, sheet structure, and last update date.
2. Search for new policies since the last update.
3. Re-check high-salience existing rows for status changes — especially
   export bans and price ceilings, which lapse quietly.
4. Search official sources by country and implementing agency.
5. Search FAO / WFP / IFPRI / IPC / FEWS NET / World Bank Food Security
   Update.
6. Search local and international news.
7. Add new rows with sources and caveats.
8. Update existing rows where details/status changed.
9. Mark expired, superseded, unverified, or excluded rows clearly.
10. Remove Afghanistan and Pakistan from SAR if present.
11. Confirm every row has a non-blank (Category, Subcategory) pair in the
    closed v6 enum.
12. Confirm every row is a government action, not a hazard description.
13. Confirm each row's `Reason` names the shock it responds to.
14. For EAP, confirm the `World Bank PICs only (12)` view contains
    exactly 12 members. Fewer means a country name drifted from
    `references/country_names.md` — fix the spelling, not the view.
15. Add an `Update_Audit` note summarizing window, searches, additions,
    uncertainties, and excluded candidates.

# Suggested search queries

Substitute country names, local-language terms, agency names, and dates.

## General

- `[country] food security crisis 2026 government response`
- `[country] food prices 2026 government measures`
- `[country] rice price 2026 government`
- `[country] wheat flour subsidy 2026`
- `[country] cooking oil price control 2026`
- `[country] food export ban 2026`
- `[country] fertilizer subsidy 2026`
- `[country] strategic grain reserve release 2026`
- `[country] drought emergency agriculture 2026`
- `[country] flood crop damage compensation 2026`
- `[country] cyclone agriculture recovery 2026`
- `[country] heatwave crop losses government 2026`
- `[country] school feeding program expansion 2026`
- `[country] food voucher program 2026`
- `[country] food import tariff suspension 2026`
- `[country] livestock feed subsidy drought 2026`
- `[country] locust armyworm control 2026`
- `[country] El Nino food security response 2026`

## Official-source targeted

- `site:gov [country] food security 2026`
- `site:gov [country] food price 2026`
- `site:gov [country] fertilizer subsidy 2026`
- `site:gov [country] export ban rice 2026`
- `site:gov [country] gazette food 2026`
- `site:gov [country] drought emergency declaration 2026`
- `site:agriculture.* [country] 2026`
- `site:gov [country] national disaster management agriculture 2026`

## International trackers

- `World Bank Food Security Update [country] 2026`
- `IFPRI food export restrictions tracker [country] 2026`
- `FAO GIEWS country brief [country] 2026`
- `WFP [country] food security 2026`
- `IPC Cadre Harmonisé [country] 2026`
- `FEWS NET [country] 2026 outlook`
- `AMIS market monitor [country] 2026`
- `FAO food price index policy response 2026`

## Local implementation agencies

- `[country] ministry of agriculture food price April 2026`
- `[country] food security task force 2026`
- `[country] grain marketing board procurement 2026`
- `[country] consumer protection agency food prices 2026`
- `[country] customs food import duty 2026`
- `[country] disaster management agency crop losses 2026`
- `[country] meteorological service drought agriculture 2026`

# Update memo

After each region's update, produce a concise memo with:

1. Workbook name
2. Update window
3. Rows added
4. Rows revised
5. Rows marked expired/superseded/excluded
6. Countries with material new activity
7. Countries searched where no verified policy was found
8. Dominant shock channels observed in the region this cycle
9. Unresolved uncertainties and follow-up items
10. Any changes that may affect HTML dashboard generation

Every material claim should be traceable to a workbook row and source.

# Quality-control rules

Before finalizing:

- All source URLs open or are otherwise documented.
- Each policy row is assigned to the correct country.
- **Every row has both `Category` and `Subcategory` populated**, and the
  pair is in the closed `Taxonomy` enum.
- **Every row is a government action, not a hazard description.**
- Every crisis-triggered row names its shock in `Reason`.
- `Reduce consumption - higher prices` is used only for price-increase
  mechanisms; `Reduce consumption - restricting quantities` only for
  rationing, purchase caps, and quantity limits.
- Afghanistan and Pakistan are not in SAR.
- EAP's `World Bank PICs only (12)` view contains exactly 12 members.
- Export bans and price ceilings have their expiry/status re-verified.
- Long policy descriptions are concise but specific.
- Exact dates are not invented.
- Proposed measures are not misclassified as active.
- Regional-summary rows are clearly marked as such.
- `poetry run po text build-policy-addons --region <r> --tracker food`
  runs cleanly against the updated workbook.

# Style

Be conservative, precise, and evidence-driven. Prefer `not found` or
`uncertain` over speculation. Preserve useful uncertainty in the
workbook rather than hiding it. The goal is not to maximize the number
of policies; the goal is a reliable, auditable tracker and a dashboard
that can be updated periodically without schema drift.
