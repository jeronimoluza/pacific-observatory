# Phases 6 + 8 — end-to-end test, then report and persist

## Phase 6 — Automated end-to-end test

**Gate: a source ships if and only if the probe passed AND the test run returns ≥ 5
valid rows.** 0–4 rows fails — record it in the skipped list with a hypothesis rather
than shipping it.

Both scaffoldings test through `python run.py prices collect --source <name>` (spiders
add `--max-items 5`). The full harness — the macOS `pkill` pattern, batching limits,
per-scaffolding record checklists, and the direct-import dev loop for fetchers — is in
`../testing.md`.

One check worth doing by eye every time: **compare the first extracted price against the
rendered page.** Minor-unit platforms produce silent 100× / 1000× errors that pass every
structural assertion.

## Phase 8 — Report and persist

Output the summary **to chat**. Then make sure everything that must outlive the session
is in-tree.

### The report

- **Working sources by `analytical_role`** — name, country, `source_key` or spider name,
  row count from the test run, one sample record.
- **Skipped sites** — name, URL, reason, using the bucket names from Phase 3 / 3-fetcher
  so they stay searchable. Include sources that probe-passed but failed the ≥5-rows bar,
  with the row count and a one-line hypothesis.
- **COICOP coverage table** — 13 rows, which onboarded source(s) cover each division, at
  what cadence, via which `analytical_role`. `—` for uncovered. Distinguish *price-level*
  coverage (retailer_sku / official_avg / tariff / aggregate_proxy) from *index* coverage
  (cpi_benchmark) — both matter, different PPP layers.
  - **Division grain overstates coverage** — it reads "covered" off a single SKU. When
    the run targeted specific commodities or leaves, report at **leaf grain** against the
    worklist in `src/prices/build/leaf_support.py`. Division tables orient; leaf tables
    decide what to do next.
- **Depth-audit outcomes** from Phase 0.5 — for each targeted commodity, say explicitly
  whether it was a *depth gap* (and which spider needs deepening), a *sourcing gap* (and
  what you onboarded), or a *structural absence* (and why retail discovery can't fix it).
  This is what stops the next session re-chasing the same item.
- **Next gaps to target (priority order)** — see the residual-source note below.

### The cost line — emit this every run, always

```
cost: files_read=<n> bytes_read=<n> probes_run=<n> agents_spawned=<n> sources_shipped=<n>
```

An agent cannot introspect its own token count, so this is the proxy that carries the
objective: *fewest total billed tokens across the whole run, per verified source
onboarded.* `bytes_read × agents_spawned` tracks billed tokens closely enough to rank two
designs. Count every sub-agent, and count the bytes they read, not just yours.

**This is an unverified assumption** until one external calibration against real token
counts off a session. Say so if you quote it as a measurement.

### What persists, and where

| What | Where it persists |
|---|---|
| Sources that worked | the manifests, under `src/prices/configs/<region>/<subregion>/<country>/` |
| **Every candidate probed — pass or fail** | `../probe_log/<run_id>-<country>.jsonl` |
| Candidates found, dead ends confirmed, local context | `../inventories/<region>/<country>.md` |
| A new blocker *class* or a new tell nothing above describes | `../blocker_classes.md` |

**The probe log is not optional and it is not the blocker list.** One row per candidate,
shipped or not. A win is a YAML manifest and a dead end used to be a markdown bullet,
which is why no run could learn from the last one. Positives and negatives now share a
schema. Append with `scripts/probe_log.py append` — it refuses a `blocked` verdict that
names no lever.

Do **not** append per-host entries to `blocker_classes.md`. That file holds class
doctrine only — which CDN families behave how, which tell means what. Per-host facts go
in the log.

### Inventory writeback

Write `../inventories/<region>/<country>.md` from the discovery output. Two requirements,
because this file is what the *next* run trusts instead of searching:

- Open with `_Inventory written: YYYY-MM-DD_` under the H1. An undated inventory cannot
  be aged, so a later run redoes the work to know whether to believe it.
- **Write the dead ends down as rows.** "No online supermarket found", "no marketplace
  with a reachable seller directory", "no NSO price table published" — a search that came
  back empty is a finding. Match the existing style: a row whose source name states the
  negative, reason in Notes.

Those negative rows are also probe-log candidates with `lever_tried: null`, so they land
in the recheck view and the `recover` route picks them up. "No online supermarket found"
is exactly the claim the Botswana sweep proved false three times in four.

Between the manifests, the probe log and the inventory, the next session can reconstruct
what happened without the chat log. Nothing about a run should depend on a note-keeping
tool the next operator may not have.

---

## Residual-source priority (after the first pass)

Once the easy fetcher wins have landed (REST APIs, public XLSX / PDF dumps), residual
deferred sources almost always fall into three buckets:

1. **Cloudflare-protected listing aggregators** (real-estate, classifieds) — needs
   `scrapy-playwright` + stealth + a new `scrapy_listing` template
2. **SPA telco / utility plan pages** (Singtel, StarHub, M1 in SG; equivalents elsewhere)
   — needs `scrapy-playwright`
3. **Akamai-protected SKU retailers** (Cold Storage, NTUC parallel brands) — same stack
   as #1, lower marginal value if FairPrice-class chains are covered

Prioritise: **gap-COICOPs first** (any source whose COICOP code is not yet covered;
PropertyGuru-class rental aggregators usually sit here at 04.1.1). This ranking assumes
**established coverage**, which is right here — a country only reaches a residual pass
after its easy sources have landed. **Redundancy second**, and only after the anti-bot
template already exists for a higher-priority site: cracking Cloudflare twice before the
first template lands is wasted effort.

Do not bundle these into a routine country onboarding. Each is its own effort.

## Open design question

**Headline CPI has no slot in IndexObservation.** The schema requires `coicop_code`
(01–13), but PPP / inflation nowcasting wants the *all-items* headline index too.
SingStat publishes it as series `1`; we drop it because there is no sanctioned sentinel.
Options: `coicop_code: "00"` for all-items, a separate `series_label` column, or a third
schema. Until decided, fetchers drop the headline row. Surface it with the user if it
comes up.
