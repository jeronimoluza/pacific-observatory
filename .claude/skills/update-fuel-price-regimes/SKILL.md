---
name: update-fuel-price-regimes
description: "Research and write the per-region fuel price-regime configuration that drives Tab 1 (Country Pricing Regimes) of the fuel policy dashboard, and update the matching `carry_forward` flags on the per-source YAML configs. Trigger when the user wants to add a new region's regime data, refresh an existing region after a policy change (subsidy reform, cap reimposed, freeze lifted), fix wrong regime pills on Tab 1, add reform-pill annotations, or align `carry_forward` flags with reality. Also use when the user says things like 'fix the regime for X', 'X changed their fuel subsidy', 'add price regime data for region Y', 'why does country X show as Market when it's actually price controlled', 'update Tab 1 country pricing regimes', or references `src/fuel/configs/_publish/<region>.yaml`. Always covers the four products Gasoline, Diesel, LPG and Kerosene — never a subset. Mirrors the pattern shipped for LAC and ECA."
---

# Update Fuel Price Regimes

Maintain the per-region YAML that classifies each country's fuel price regime
(Market vs Price Control) for the fuel policy dashboard's Tab 1 *Country
Pricing Regimes* table, plus the `carry_forward` flag on each source config
that controls how the build stage handles observation gaps.

There are two reasons to use this skill:

1. **Discovery** — onboarding a new region (e.g. the ECA pass mirroring the
   LAC pass), or filling in coverage that was previously missing.
2. **Update** — a country reforms (decree, subsidy elimination, freeze
   lifted, cap reimposed) and the existing classification or `carry_forward`
   no longer matches reality.

The pipeline contract below is identical for both modes; the only difference
is scope.

## Hard contract: four products, always

Tab 1 renders one row per country with one column per product:

| Product  | Notes |
|----------|-------|
| Gasoline | Most-sold octane grade by retail volume (regular/95 in most markets). |
| Diesel   | Road diesel (Eurodiesel, B7 in EU; standard diesel elsewhere). Includes off-road / coloured diesel only if there is no other regulated diesel. |
| LPG      | Autogas + bottled household LPG. If the country regulates only one, classify the regulated one. |
| Kerosene | Aviation kerosene / paraffin. Often Market in most countries (jet fuel rarely consumer-regulated). |

**You always classify all four products, even if a country has no LPG or no
kerosene retail market.** Use `Market` + `subsidy: false` as the neutral
default when a product is absent or genuinely unregulated. Never leave a
product out — the table renders a blank cell when a product key is missing
and that looks like a data bug.

## Files this skill writes

```
src/fuel/configs/_publish/<region>.yaml          ← regime_overrides + regime_notes
src/fuel/configs/<region>/**/*.yaml              ← carry_forward (source-level
                                                  and optional per-product)
```

Region slugs: `eap | eca | lac | menaap | sar | ssa | pacific`. Look at the
`src/fuel/configs/<region>/` directory layout to confirm subregion and
country structure before editing.

## Reference data

| Path | Purpose |
|---|---|
| `data/fuel/_reference/worldbank/subsidies_price_controls.csv` | WB 2024 baseline pricing-regime dataset. Read this first per ISO3 before researching anything online; many countries are already correctly classified and need no override. |
| `data/fuel/_reference/imf/subsidies_*.{xlsb,xlsx}` | IMF Fossil Fuel Subsidies — drives the "Subsidised" badge in Tab 1. You don't write to this; you just note when to align the override `subsidy` flag with IMF reality. |
| `src/fuel/configs/_publish/lac.yaml` | Canonical reference for `regime_overrides` + `regime_notes` shape. Read it before writing a new region. |
| `src/fuel/publish_html.py` (function `gen_policy_html`) | How the YAML fields render. Useful when in doubt about a schema field. |

## Workflow

### Step 1 — Determine scope and read baselines

- **Discovery mode:** the user says "do this for region X" (like ECA). Pull
  the full ISO3 list for the region from the source YAMLs in
  `src/fuel/configs/<region>/`. Read the WB 2024 row for every ISO3
  (countries missing from the WB CSV — small territories, Belarus, Western
  European micros — will need explicit overrides).
- **Update mode:** the user names one or a few countries that changed regime
  ("Brazil just deregulated diesel", "Croatia reimposed the cap"). Read the
  current entry in `_publish/<region>.yaml` (if present) and the WB 2024 row
  to know the baseline you're correcting.

Convert any relative dates in user messages to absolute dates before saving
anything — memory and reform pills should outlive the conversation.

### Step 2 — Research regime per (country, product)

For each (country × product) cell that needs work, produce three facts:

1. **Regime** — `Market` or `Price Control`. Price Control covers any of:
   government-set retail price, biweekly/weekly cap formula, stabilization
   fund actively used, frozen retail by decree, hybrid pseudo-regulation
   (e.g. executive pressure on a state-owned refinery).
2. **Subsidy presence** — `true` if there is any consumer-side subsidy: cap
   absorption, excise rebate, farmer rebate, household LPG subsidy, implicit
   below-cost pricing, stabilization-fund payout. `false` otherwise.
3. **Reform pill (optional)** — short label (≤30 chars), 1-2 sentence note,
   and 1-2 primary-source URLs. Attach a reform pill whenever a country has
   had a notable 2024-2026 change for that product. Leave it off when
   nothing has changed.

Source preference, in order:
- Country regulator / ministry primary pages (e.g. anre.md, epdk.gov.tr,
  erc.org.mk, vlada.gov.hr).
- Reputable wire news (Reuters, Bloomberg, AP, Financial Times).
- Country-specialized news outlets and policy think tanks.
- Avoid `globalpetrolprices.com` (blanket exclusion per project convention).

When researching a region with many countries (5+), spawn parallel research
agents per subregion to keep this tractable; assemble back into one YAML.

### Step 3 — Write `regime_overrides` (only where WB-2024 is wrong)

You only include a country in `regime_overrides` if at least one product cell
disagrees with what the WB CSV would render. The override fully **replaces**
the WB-derived per-product classification for that ISO3, so when you include
a country you must spell out all four products.

```yaml
regime_overrides:
  HRV:
    Gasoline: {regime: Price Control, subsidy: true}
    Diesel:   {regime: Price Control, subsidy: true}
    LPG:      {regime: Price Control, subsidy: true}
    Kerosene: {regime: Market,        subsidy: false}
```

Schema:
- `regime` — one of `Market` or `Price Control`.
- `subsidy` — boolean. Used to compute the scatter-view classification
  (`Price Control + Subsidies`). The Tab 1 "Subsidised" badge itself is
  driven by the IMF data, not by this flag — but keep this aligned with IMF
  reality where possible.

Reasons you'd write an override:
- Country is **not in the WB CSV** (Belarus, Gibraltar, Isle of Man,
  Liechtenstein, Monaco, San Marino, etc.) — write the full row from scratch.
- Country **reformed in 2025-2026** and WB still reflects the old regime
  (Bolivia subsidy elimination Dec-2025, Türkiye FPSM reinstatement
  Mar-2026, Croatia cap reimposed Mar-2026, Romania OUG 19/2026, etc.).
- WB lumps products that move independently (Russia: gasoline + diesel +
  kerosene managed, LPG genuinely deregulated; Ecuador: Super deregulated,
  Extra/Ecopaís band-controlled, diesel reformed Sep-2025).
- WB classifies the country as Market because the formal regime is
  deregulated, but the **de facto** state intervention is dominant (Türkiye
  SCT/FPSM stabilization, Montenegro biweekly Ministry tariff).

Always write a short comment above each entry explaining why you overrode.

### Step 4 — Write `regime_notes` (every country you touch)

`regime_notes` is what populates the popovers when a user clicks a regime
pill. Include an entry for **every country in your scope** — both those you
overrode and those whose WB classification is fine. The pill always exists;
the popover only adds quality if you provide attribution.

```yaml
regime_notes:
  HRV:
    Gasoline:
      classification_sources:
        - "WB 2024 pricing-regime dataset (mech=2, biweekly cap since Oct-2021)."
        - { label: "vlada.gov.hr — Uredba o najvišim cijenama",
            url: "https://vlada.gov.hr/..." }
      reform:
        label: "Cap Jul-25 → Mar-26"
        note: "Croatia ended its 3-year biweekly cap regime in July 2025, then reimposed the Uredba on 9-Mar-2026 ..."
        sources:
          - { label: "Croatia Week — cap & Iran-war volatility",
              url: "https://www.croatiaweek.com/..." }
    Diesel:
      classification_sources:
        - "WB 2024 pricing-regime dataset (mech=2). Diesel covered by the same Uredba."
    LPG:
      classification_sources:
        - "Eurosuper-95, Eurodiesel, blue diesel, LPG all covered by the current decree."
    Kerosene:
      classification_sources:
        - "Aviation kerosene — Market; no domestic retail cap."
```

Schema:
- `classification_sources` — list of strings or `{label, url}` objects.
  Rendered as a `<ul>` of links under the primary pill popover. If omitted,
  the pill shows a generic fallback ("Classification source: WB Energy
  Pricing Regimes Dataset 2024") — usable but worse.
- `reform` — optional. Renders as a secondary dashed-outline pill next to
  the primary pill. Contains `label`, `note`, and `sources` (same shape as
  `classification_sources`).

**Cell discipline:** repeating the same `classification_sources` text on
Gasoline and Diesel is fine and expected when one decree covers both. Don't
artificially split. Don't write a `reform` pill if there isn't one — empty
pills look broken.

### Step 5 — Apply `carry_forward` per source YAML

`carry_forward` lives on each source config in `src/fuel/configs/<region>/`
and is consumed by the build stage (`src/fuel/process.py:_load_source_frame`).
The semantics matter and are independent of the Tab 1 classification:

| Source nature | `carry_forward` | Why |
|---|---|---|
| **State-set decree** scraped directly (price freeze, weekly decree, Tariff Council, Belneftekhim) | `true` | A gap in the scrape means *the decree still holds*. Fill forward until the next observation. |
| **Observed retail aggregator** (autotraveler, tolls.eu, station-level averages, OFT bulletins, regulator's *observed-average* publications) | `false` | A gap is a missing observation, not a policy state. Don't invent prices. |

You can have a state-controlled regime (Tab 1 = Price Control) and still set
`carry_forward: false` when the *source* is an aggregator. Tab 1 classifies
the **policy**; `carry_forward` classifies the **data feed**. They are
correlated but not identical — get this distinction right or the time series
will look wrong on Tab 3.

**Mixed-regime sources** — if one source publishes prices for products under
different regimes (e.g. a Russian feed that includes gas/diesel/kerosene
under damper + LPG deregulated; an Ecuador feed where Super is market but
Extra/Diesel/LPG are controlled), use the per-product override. Schema (Phase
1, shipped 2026-05-12):

```yaml
carry_forward: false   # source-level default
products:
  "Premium":
    series_key: gasoline_95_plus
    carry_forward: false  # override (redundant here but illustrative)
  "Magna":
    series_key: gasoline_95
    carry_forward: true   # this product is IEPS-subsidized and decreed
```

Per-product fields override the source-level default. Omitting the field
falls back to source-level. Implementation: `src/fuel/config.py:43` and
`src/fuel/process.py:174`.

### Step 6 — Validate

Run this exact smoke test from the repo root after every edit:

```bash
python -c "
from src.fuel.config import load_all_source_configs
from src.fuel.publish import _load_publish_config
configs = load_all_source_configs(region='<REGION>')
pub = _load_publish_config('<REGION>')
print(f'{len(configs)} source configs OK')
print(f'overrides: {sorted(pub[\"regime_overrides\"])}')
print(f'notes:     {sorted(pub[\"regime_notes\"])}')
"
```

Then regenerate the dashboard:

```bash
poetry run po fuel publish --region <REGION>
# or, until the new CLI lands:
poetry run python -m src.cpi.fuel_prices publish
```

Open `outputs/fuel/<region>/fuel_policy_dashboard.html` and visually verify:
- Tab 1 *Country Pricing Regimes* table renders all four product columns
  for every country in the region.
- Pills with a dashed outline (the reform pills) appear for the countries
  where you added a `reform` block.
- Clicking a primary pill shows the `classification_sources` popover (not
  the generic WB fallback) for every country you wrote a `regime_notes`
  entry for.
- Tab 3 *Economies Fuel Prices* time series for any country whose
  `carry_forward` you changed shows the new behaviour (flat plateaus vs
  observation-only).

## Decision rules cheat-sheet

When in doubt:

| Situation | Regime | Subsidy | carry_forward |
|---|---|---|---|
| EU-aligned market (BGR, POL, GIB, IMN, LIE, MCO, SMR) | Market | false unless temporary VAT/excise relief is active | false (observed retail) |
| Weekly/biweekly state cap (HRV, MKD, MDA, SRB, MNE, ALB post-Mar 2026, RO Apr-Jun 2026) | Price Control | true | source-dependent (false if you scrape autotraveler / observed averages; true if you scrape the decree feed itself) |
| State monopoly (BLR, AZE) | Price Control | true (implicit cross-subsidy via state-owned refining) | true |
| Damper / hybrid (RUS) | Price Control per product (LPG remains Market) | true | source-dependent |
| De facto control via excise manipulation (TUR FPSM) | Price Control | true | false (autotraveler is observed retail) |
| Subsidy reform completed (BOL Dec-2025, ECU diesel Sep-2025) | Re-classify per WB next release | flag transition in reform pill | follow the new regime |
| Country missing from WB CSV | Write the full override from scratch | use IMF data + research | source-dependent |

## Examples in this repo

- **LAC pass (shipped 2026-05-12):** `src/fuel/configs/_publish/lac.yaml`
  — 19 sources, 5 regime overrides, 12 countries with reform pills. Also
  flipped `carry_forward` on argentina/datos_argentina.yaml,
  brazil/anp.yaml, chile/cne_bencina.yaml.
- **ECA pass (shipped 2026-05-13):** `src/fuel/configs/_publish/eca.yaml`
  — 24 sources, 13 regime overrides, 26 reform pills across 23 countries.
  Flipped `carry_forward: false` on 22 of 24 sources (kept `true` only on
  belarus/autotraveler.yaml and south_caucasus/azerbaijan/autotraveler.yaml).

Read the LAC config first as the cleanest reference; read ECA when you need
to handle a region with many micro-states absent from the WB CSV.

## Why this skill exists

The Tab 1 regime table is the most-read part of the policy dashboard. WB
2024 is the canonical baseline but goes stale fast — Bolivia, Ecuador,
Croatia, Türkiye, Romania, Albania all moved meaningfully between the WB
reference date and 2026. The dashboard's value depends on whether a reader
opening it today sees current reality. That requires periodic per-country
research, careful per-product classification, and disciplined `carry_forward`
treatment so the time series don't lie about gaps.

Captured here so the next regional pass is a 1-2 hour job instead of a
2-day archaeology project.
