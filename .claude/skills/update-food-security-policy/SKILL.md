---
name: update-food-security-policy
description: "Update the regional Food Security Policy trackers and regenerate the per-region addon dashboards that feed `po text publish --tracker food`. Trigger when the user wants to refresh food-security policy data for EAP / ECA / MENAAP / SAR / LAC / SSA, asks to 'update the food security tracker', references `data/text/policy_tracker/food_security/<region>.xlsx`, or wants to publish the Food Security Policy + EPU dashboard for a region. Orchestrates: (1) research-driven workbook updates per `references/master_prompt.md` (per-country search across food prices, production shocks, trade measures, input costs and climate/weather shocks; two-part demand/consumption typology; SAR excludes AFG/PAK; EAP includes the 12-PIC view), (2) `po text build-policy-addons --region <r> --tracker food` to convert workbooks into HTML addons under `src/text/plotting/addons/`, (3) `po text publish --region <r> --tracker food` to render the final four-tab dashboard. Stops after publish — does NOT modify any other pipeline state."
---

# Update Food Security Policy

Refresh the regional Food Security Policy trackers and rebuild the
standalone HTML dashboards that the `publish` command embeds as iframe
srcdoc.

This is the food-security sibling of `update-fuel-crisis-policy`. Same
pipeline, same workbook schema, **same closed v6 taxonomy** — only the
crisis lens and the research brief differ. The `--tracker food` flag
keeps every path, filename and dashboard label separate from the fuel
tracker so the two never overwrite each other.

## When this skill applies

- Update food-security policy data for one region
  (`eap | eca | menaap | sar | lac | ssa`) or all six.
- Republish a region's Food Security Policy + EPU dashboard after
  research is done.
- User says "the EAP food security tracker is stale", "regenerate the
  SAR food policy dashboard", "add export bans to the tracker", or
  references `data/text/policy_tracker/food_security/`.

For a one-off fix to a single Excel row (no research), the user can edit
the workbook directly and run step 3 + step 4 below — no skill needed.

## Scope boundary — what counts as food-security policy

A valid row is a **government / regulator / SOE / official regional-body
action** responding to a food-security or food-price shock. The shock
may originate anywhere in the food system:

- food price inflation, staple price spikes, retail food affordability
- production shocks: **drought, extreme heat, flood, cyclone, frost,
  pest and disease outbreaks, crop failure, livestock losses**
- input cost or availability shocks: **fertilizer, seed, feed, fuel for
  agriculture, agricultural credit, irrigation water**
- trade and supply disruption: export bans, import dependence, shipping
  and freight, port closures
- humanitarian food insecurity: IPC-phase deterioration, famine risk,
  acute malnutrition

**Climate and weather terms belong here as the trigger, not the
measure.** A heatwave is not a policy row. A *drought emergency
declaration*, a *livestock destocking subsidy*, or an *irrigation
emergency fund responding to that drought* is. Record the shock in the
`Reason` column as the evidence link.

Exclude: long-horizon agricultural development strategy with no crisis
link, routine annual budget lines, private-sector-only actions, and
analytical commentary.

## Pipeline (canonical)

```
data/text/policy_tracker/food_security/<region>.xlsx
   |  (research + edit per references/master_prompt.md)
   v
data/text/policy_tracker/food_security/YYYY-MM-DD/excel/<region>.xlsx   (dated snapshot)
   |
   v
po text build-policy-addons --region <r> --tracker food
   |  (converter: src/text/plotting/policy_dashboards.py)
   v
src/text/plotting/addons/food_security/<region>_policy_addon.html
   |
   v
po text publish --region <r> --tracker food
   |  (orchestrator: src/text/publish.py:run_publish)
   v
outputs/text/dashboards/food_security/<region>_policy_dashboard.html
```

The other three tabs (Uncertainty Topics, Topics EPU, Actors EPU) come
from the **shared keyword pack**, not from the workbook:

```
src/text/analysis/keywords/<lang>/topics/{core,food}.json
src/text/analysis/keywords/<lang>/actors/{core,food}.json
   |  (one file per theme; en/ is the source of truth for group names)
   v
po text build --region <r>
   |  (annotator: src/text/analysis/annotate.py — computes EVERY theme)
   v
outputs/text/<r>/**/uncertainty_attribution/{topics,actors}.csv
outputs/text/<r>/**/epu/{topics,actors}_epu.csv
```

One build serves every tracker. The CSVs carry all 43 topics and 24
actors; `--tracker` selects which slice a dashboard displays, per the
`themes` / `extra_topics` / `extra_actors` keys in
`src/text/plotting/trackers.py`. Food shows 18 topics and 11 actors: its
own 12 + 7, plus the macro-context groups it shares with fuel.

Because the definitions are shared, a group named on two dashboards is
the same series on both — `inflation_prices` on the food dashboard is
the `inflation_prices` on the fuel dashboard.

The fuel tracker's paths (`policy_tracker/<region>.xlsx`,
`addons/fuel/<region>_policy_addon.html`,
`dashboards/fuel/<region>_policy_dashboard.html`) are untouched by any
`--tracker food` run.

## Step 1 — Update the workbook

Open `data/text/policy_tracker/food_security/<region>.xlsx`. The research
protocol — search window, per-country search, per-implementing-agency
search, multilingual queries, the shock-trigger evidence rule, the
two-part `Reduce consumption` typology, source hierarchy, evidence
standards, QC list — is in `references/master_prompt.md`.
**Open and follow that file.** Do not duplicate its content here.

All workbooks share the fuel tracker's sheet layout: `Policies` (the
policy rows the converter reads), `Taxonomy` (closed 6×31
(Category, Subcategory) enum, treat as read-only, **identical to the fuel
tracker's**), `Update_Audit` (notes).

Every Policies row must carry both `Category` (1 of 6) and `Subcategory`
(1 of 31, constrained by Category) from the closed v6 enum. The legacy
`Label` column is retained for audit but is **not rendered** by the
dashboard.

The v6 enum was designed broadly enough to cover food security without
change — `agriculture` and `social protection` carry most of the load,
with `regulatory and trade facilitation reforms` for export bans and
emergency declarations. **Do not extend or edit the Taxonomy sheet.**

Region-specific rules the converter enforces on top of that:

| Region | Hard rule |
|---|---|
| `eap` | Exposes a `World Bank PICs only (12)` country-view: Fiji, Kiribati, RMI, FSM, Nauru, Palau, PNG, Samoa, Solomon Islands, Tonga, Tuvalu, Vanuatu. |
| `eca` | Rows matching coverage-audit phrases (`scope definition`, `no verified current discretionary fuel relief`, `source gap`, …) are auto-excluded from the dashboard. Keep them in the workbook as audit notes. |
| `menaap` | Afghanistan & Pakistan belong here, not in SAR. |
| `sar` | Afghanistan & Pakistan are auto-excluded; do not add them. |
| `lac` | — |
| `ssa` | — |

Save back to the same filename (`<region>.xlsx`, no date suffix).

## Step 2 — Archive the dated snapshot

**After every workbook edit is finished and saved** — and specifically
**after** any parallel research agents have returned and you have
confirmed the live `.xlsx` mtimes reflect their writes:

```bash
DATE=$(date -u +%Y-%m-%d)
mkdir -p data/text/policy_tracker/food_security/$DATE/excel
cp data/text/policy_tracker/food_security/<region>.xlsx \
   data/text/policy_tracker/food_security/$DATE/excel/<region>.xlsx
```

**Ordering rule (do not snapshot early):** in a parallel run, do NOT
snapshot at job dispatch — the live files still hold the previous run's
content. Wait until every region's editor has reported done, then
snapshot once. Identical file sizes across all regions is the canonical
"snapshotted too early" smell.

Skip this step only when you didn't change the workbook.

## Step 3 — Build the addon HTML

```bash
poetry run po text build-policy-addons --region <r> --tracker food
```

The converter reads
`data/text/policy_tracker/food_security/<region>.xlsx`, normalizes alias
headers, and writes
`src/text/plotting/addons/food_security/<region>_policy_addon.html`.

**Verify**: the run printed `included rows: N` with N > 0, no errors,
and the HTML mtime is fresh
(`ls -la src/text/plotting/addons/food_security/<region>_policy_addon.html`).

## Step 3b — Rebuild the EPU/Topics numbers (only when keywords change)

Skip this on a routine workbook refresh — the three EPU tabs read
already-computed CSVs. Run it only after editing
`src/text/analysis/keywords/<lang>/{topics,actors}/food.json`:

```bash
poetry run po text build --region <r>
```

There is no keyword-set flag: the build computes every theme in one
pass, so a rebuild refreshes the fuel and food numbers together. Editing
any theme file changes the cache hash and triggers the rebuild.

Fallback is **per theme**: a language with its own `core.json` but no
`food.json` keeps its translated core and falls back to English only for
food. `epu.json` (the economic × policy × uncertainty gate) is a single
flat file shared by every tracker, so the EPU denominator is identical
across them.

**Verify**: `uncertainty_attribution/topics.csv` has 43 `*_framing`
columns and `actors.csv` has 24 — all themes, with the dashboard doing
the selection.

## Step 4 — Publish

```bash
poetry run po text publish --region <r> --tracker food
```

Renders the **full four-tab dashboard** — the Food Security Policy tab
plus the three EPU/Topics tabs (Uncertainty Topics, Topics EPU, Actors
EPU), exactly as the fuel dashboard does. Output:
`outputs/text/dashboards/food_security/<region>_policy_dashboard.html`.

Add `--skip-database-status` to skip the slow global database-status
refresh when you only need the dashboard (prototype / iteration runs).

## Step 5 — QC

- Every Policies row has both `Category` and `Subcategory` populated,
  and the pair is in the closed v6 enum (see `Taxonomy` sheet).
- Legend shows the 6 v6 categories — not the legacy Label values.
- Filter pair (Category + cascading Subcategory) is functional.
- **All four tabs render**: Food Security Policy, Uncertainty Topics,
  Topics EPU, Actors EPU.
- Tab 1 is titled `Food Security Policy`, not `Fuel Crisis Policy`.
- The EPU/Topics tabs show 18 topics and 11 actors — the food selection
  from `trackers.py`, not all 43/24 the build computes.
- SAR has no Afghanistan / Pakistan rows.
- EAP shows `World Bank PICs only (12)` in the country-view dropdown.
- Every row whose trigger is a climate/weather shock names that shock in
  `Reason` with a source.
- No row is a bare hazard description with no government action.
- Source URLs open (spot-check 3–5).
- The fuel artifacts are untouched: `addons/fuel/<region>_policy_addon.html`
  and `outputs/text/dashboards/fuel/<region>_policy_dashboard.html` mtimes
  unchanged.

## Output format (after a full run)

```
## Food Security Policy refresh: <region>
- Workbook: data/text/policy_tracker/food_security/<region>.xlsx  (last edited: <mtime>)
- Snapshot: data/text/policy_tracker/food_security/YYYY-MM-DD/excel/<region>.xlsx
- Addon:    src/text/plotting/addons/food_security/<region>_policy_addon.html
            (rows=<n>, excluded=<n>, countries=<n>)
- Final:    outputs/text/dashboards/food_security/<region>_policy_dashboard.html
- New rows: <n>; revised rows: <n>; superseded/excluded: <n>
- Countries with no verified measure found: <list>
- Open follow-ups: <bulleted list>
```

## Hard rules

- **Never** invent measures or fill gaps speculatively. Mark thin rows
  as `Unverified` / `Needs follow-up` instead of guessing.
- **Never** delete or modify Excel rows the user didn't authorize.
  Reclassify or mark `Superseded` / `Excluded` instead.
- **Never** edit the `Taxonomy` sheet or invent Category/Subcategory
  values outside the closed v6 enum.
- **Never** add Afghanistan or Pakistan to the SAR workbook.
- **Never** write to `data/text/policy_tracker/<region>.xlsx` (that is
  the fuel tracker) or omit `--tracker food` from the build/publish
  commands.
- **Never** create a row for a weather/climate event alone — the row is
  the government response, the event is the `Reason`.
