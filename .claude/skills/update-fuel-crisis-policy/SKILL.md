---
name: update-fuel-crisis-policy
description: "Update the regional Fuel Crisis Policy trackers and regenerate the per-region addon dashboards that feed `po text publish`. Trigger when the user wants to refresh policy data for EAP / ECA / MENAAP / SAR / LAC / SSA, asks to 'update the policy tracker', references `data/text/policy_tracker/<region>.xlsx`, or wants to publish the Fuel Crisis Policy + EPU dashboard for a region. Orchestrates: (1) research-driven workbook updates per `references/master_prompt.md` (per-country search, two-part demand-reduction typology, SAR excludes AFG/PAK, EAP includes the 12-PIC view), (2) `po text build-policy-addons --region <r>` to convert workbooks into HTML addons under `src/text/plotting/addons/`, (3) `po text publish --region <r>` to render the final tabbed dashboard. Stops after publish — does NOT modify any other pipeline state."
---

# Update Fuel Crisis Policy

Refresh the regional Fuel Crisis Policy trackers and rebuild the standalone
HTML dashboards that the `publish` command embeds as iframe srcdoc.

## When this skill applies

- Update policy data for one region (`eap | eca | menaap | sar | lac | ssa`)
  or all six.
- Republish a region's Fuel Crisis Policy + EPU dashboard after research is done.
- User says "the EAP policy tracker is stale", "regenerate the SAR fuel
  policy dashboard", "update the policy addons", or references
  `data/text/policy_tracker/` or `src/text/plotting/addons/`.

For a one-off fix to a single Excel row (no research), the user can edit
the workbook directly and run step 2 + step 3 below — no skill needed.

## Pipeline (canonical)

```
data/text/policy_tracker/<region>.xlsx
   |  (research + edit per references/master_prompt.md)
   v
po text build-policy-addons --region <r>
   |  (converter: src/text/plotting/policy_dashboards.py)
   v
src/text/plotting/addons/<region>_fuel_crisis_policy_dashboard.html
   |
   v
po text publish --region <r>
   |  (orchestrator: src/text/publish.py:run_publish)
   v
outputs/text/dashboards/<region>_policy_dashboard.html
```

## Step 1 — Update the workbook

Open `data/text/policy_tracker/<region>.xlsx`. The research protocol —
search window, per-country search, per-implementing-agency search,
multilingual queries, the two-part `Reduce demand - higher prices` /
`Reduce demand - restricting quantities` typology, source hierarchy,
evidence standards, QC list — is in `references/master_prompt.md`.
**Open and follow that file.** Do not duplicate its content here.

All workbooks share the same sheet layout: `Policies` (the policy rows
the converter reads), `Categories` (label list), `Update_Audit` (notes).
Region-specific rules the converter enforces on top of that:

| Region | Hard rule |
|---|---|
| `eap` | Exposes a `World Bank PICs only (12)` country-view: Fiji, Kiribati, RMI, FSM, Nauru, Palau, PNG, Samoa, Solomon Islands, Tonga, Tuvalu, Vanuatu. |
| `eca` | Rows matching coverage-audit phrases (`scope definition`, `no verified current discretionary fuel relief`, `source gap`, …) are auto-excluded from the dashboard. Keep them in the workbook as audit notes. |
| `menaap` | Afghanistan & Pakistan belong here, not in SAR. |
| `sar` | Afghanistan & Pakistan are auto-excluded; do not add them. |
| `lac` | — |
| `ssa` | — |

Save back to the same filename (`<region>.xlsx`, no date suffix). Git
status / mtime is the version log.

## Step 2 — Build the addon HTML

```bash
poetry run po text build-policy-addons --region <r>
# or for all six:
poetry run po text build-policy-addons
```

The converter (`src/text/plotting/policy_dashboards.py`):
- Reads `data/text/policy_tracker/<region>.xlsx` (or any
  `*<region>*.xlsx` fallback).
- Normalizes alias headers (`Country/economy`, `Policy measure`,
  `Status/date`, etc.) into the dashboard schema.
- Maps legacy `Reduce demand` rows into the two-part typology using
  policy/description/reason text.
- Writes `src/text/plotting/addons/<region>_fuel_crisis_policy_dashboard.html`
  and `dashboard_generation_summary.json`.

**Verify**: confirm the run printed `included_rows > 0`, no entries
under `errors`, and the per-region HTML mtime is fresh
(`ls -la src/text/plotting/addons/<region>_*.html`).

## Step 3 — Publish

```bash
poetry run po text publish --region <r>
```

This calls `src/text/publish.py:run_publish`, which (for each region in scope):
1. Discovers EPU units for the region.
2. Writes `outputs/text/dashboard_data/<region>/<region>.{json,csv,xlsx,dta}`.
3. Loads the addon HTML from step 2 via
   `src/text/plotting/small_dashboard_integrated_w_policy.py:_load_addon_html`.
4. Composes the final four-tab dashboard:
   `outputs/text/dashboards/<region>_policy_dashboard.html`.

The skill may run this directly — side effects are local file writes
only.

## Step 4 — QC

Open the final HTML and confirm against the checklist at the end of
`references/master_prompt.md`. Critical items:

- No `Reduce demand` entry remains in the legend (use the two new labels).
- SAR has no Afghanistan / Pakistan rows in the bar chart.
- EAP shows `World Bank PICs only (12)` in the country-view dropdown,
  and that view contains exactly the 12 countries.
- Each row in `Country/economy` matches a real workbook row; no
  invented entries.
- Source URLs open (spot-check 3–5).

## Output format (after a full run)

```
## Fuel Crisis Policy refresh: <region>
- Workbook: data/text/policy_tracker/<region>.xlsx  (last edited: <mtime>)
- Addon:    src/text/plotting/addons/<region>_fuel_crisis_policy_dashboard.html
            (rows=<n>, excluded=<n>, countries=<n>)
- Final:    outputs/text/dashboards/<region>_policy_dashboard.html
- Reclassified `Reduce demand` rows: <n>
- New rows: <n>; revised rows: <n>; superseded/excluded: <n>
- Open follow-ups: <bulleted list>
```

## Hard rules

- **Never** invent measures or fill gaps speculatively. Mark thin rows
  as `Unverified` / `Needs follow-up` instead of guessing.
- **Never** delete or modify Excel rows the user didn't authorize.
  Reclassify or mark `Superseded` / `Excluded` instead.
- **Never** add Afghanistan or Pakistan to the SAR workbook (the
  converter auto-excludes them, but they should not be in the source
  data either).
- The deprecated `Reduce demand` label must not appear in any final
  dashboard-compatible row.
