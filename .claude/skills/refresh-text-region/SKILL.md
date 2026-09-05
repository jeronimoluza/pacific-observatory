---
name: refresh-text-region
description: "Use this skill whenever the user wants to refresh, update, or run `po text collect` against an existing region/subregion (LAC, SAR, MENAAP, EAP, ECA, SSA, Pacific) or fix a stuck text source. Trigger on phrases like 'update text data for sar', 'refresh lac text collect', 'run po text update for menaap', 'fix text source <name>', 'why is <source> at low %', or any request to bring a region's text data current. Orchestrates parallel `po text collect --country X` runs (max 4 in parallel) AND autonomously diagnoses + fixes stuck sources mid-run (broken selectors, excerpt-only article patterns, ledger pre-seeds) without asking permission for each step. Stops at collect — does NOT run build/publish. Two modes: region-wide refresh (job queue from `src/text/configs/<region>/`) or single-source fix (one named YAML)."
---

# Refresh Text Region

Run a parallel `po text collect` refresh across a region's sources, autonomously detect stuck sources during the run, diagnose them, fix configs + pre-seed failure ledgers, and report a per-country tally. Stops at collect.

## When this skill applies

- Region/subregion refresh: `update text data for sar`, `refresh lac text collect`, `run po text update for menaap`.
- Single-source fix: `fix text source <name>`, `<source> is stuck at <X>%`, `why is <source> grinding`.
- The skill assumes the region is already onboarded (sources have working YAML configs in `src/text/configs/<region>/.../`). For a fresh region with no configs yet, use the `onboard-region-newspapers` skill instead.

## Two modes

### Mode A — region/subregion refresh

Primary entry point — runs queue build + parallel launch in one shot:

```bash
bash .claude/skills/refresh-text-region/scripts/launch_refresh.sh <region> [parallelism] [max_source_seconds]
# defaults: parallelism=8, max_source_seconds=300 (5 min PER SOURCE — not per region)
```

What it does:
1. Walks `src/text/configs/<region>/.../<source>.yaml` (skipping `_0_*.yaml`) and writes the queue to `/tmp/refresh_<region>_jobs.txt`. Every source is queued as its own `country|source` line so xargs distributes them evenly across the `-P` slots.
2. Launches `xargs -P <parallelism>` against `scripts/runner.sh`, exporting `MAX_SOURCE_SECONDS` so each runner caps its own python child. Events stream to `/tmp/refresh_<region>_nohup.log`.
3. **No region-wide budget.** The orchestrator runs until the queue drains. Each source that exceeds its per-source cap is killed individually (emits `[TIMEOUT]`); the rest keep going.

Then:
4. Stream `[START]/[DONE]/[FAIL]/[STUCK]/[TIMEOUT]/[REFRESH-DONE]` events via the Monitor tool; tail per-source logs for stuck-source signals (below).
5. As stuck sources appear mid-run, fork into the diagnose+fix loop, then re-queue the source as a separate detached job.
6. After `[REFRESH-DONE]` arrives, generate the report:

```bash
poetry run python .claude/skills/refresh-text-region/scripts/render_collect_report.py <region> --parallelism <P> --max-source-seconds <S>
# → outputs/text/reports/collect/collect_<region>_<ts>.md
```

**Wall-clock estimate**: the run takes roughly `(queue_size / parallelism) * avg_source_seconds`. With -P 8 and ~30s average per source, a 200-source region is ~13 min; an 900-source region is ~56 min. The per-source cap bounds the *worst* runtime per slot, not the total.

The legacy template-based pattern in `references/orchestration.md` still works for ad-hoc tweaks but is no longer the primary path.

### Mode B — single-source fix
Skip the orchestration; jump straight to the diagnose+fix loop on the named source. Apply config fix, seed the ledger if warranted, smoke-test, report.

## Detection signals for "stuck"

A source is **stuck** when, mid-run, ANY of these is true. The skill should auto-investigate, not wait.

| Signal | How to detect |
|---|---|
| Selector-broken warning | The per-source log contains `⚠ <source>: after N article attempts, 0 were successfully scraped. Selectors may be broken — continuing anyway.` |
| Iter rate slow + sustained | tqdm progress shows >5s/it sustained for >50 iterations. Parse the latest `it/s\]` token from the log via `tr '\r' '\n' < log \| grep -oE 'Scraping articles:[^\|]*\|[^\|]*\|[^]]*\]' \| tail -1`. |
| False-CLEAR / WAF stall (auto) | The runner's built-in watchdog emits `[STUCK] <tag> (no news.csv growth for <N>s after warning; killing python)` directly to the nohup log when the selector-broken warning has fired AND target `news.csv` has shown zero size growth for `STALL_SECONDS` (default 300). See `references/orchestration.md → Watchdog semantics`. The kill is automatic; the operator's job is just to triage which Pattern applies. |

**Do NOT flag from `po text status` alone**: a source showing "2d ago" may just mean the site is genuinely quiet. Only the in-run signals above are reliable. (See `references/known_stuck_patterns.md` for the four classes seen in the wild.)

## Diagnose + fix loop (autonomous)

When a stuck source is detected, follow `references/diagnose_loop.md`. The loop is:

1. **Kill the running collect for that source** — kill the python PID ONLY, never the xargs wrapper shell. Use `scripts/kill_collect_python.sh <source>`.
2. **Probe**: read pending = urls.csv − news.csv. Stratified-by-year sample: WP API content.rendered + HTML against configured `body` selector + 3-4 fallback selectors.
3. **Classify** into one of four patterns from `references/known_stuck_patterns.md` and apply the matching fix.
4. **Smoke-test**: `po text collect --country X --source Y --max-articles 5`. The fix is green when `Articles Scraped > 0` (or `Skipped (ledger): N` matches the seeded count and `Thumbnails Discovered: 0` because the source is caught up).
5. **Re-launch the source as a detached job** so it joins the rest of the run.

The four patterns:
- **Empty-body posts** (cubanet/proceso/dagblad) → keep selector good for new articles, **pre-seed the ledger** with all pending URLs (`last_status=NO_BODY`).
- **Wrong selector, body present** → update YAML `article.body` to the discovered selector + add date selector.
- **Cloudflare / rate-limit** → escalate; do not auto-fix; mark source as DEFERRED in the report.
- **Site genuinely silent** (no new articles, but selector works) → skip; not a fix-needed condition.

## Critical operational rules — do not skip

These rules came from real incidents on 2026-05-04. Bake them into the workflow.

1. **xargs SIGTERM gotcha**: when killing a stuck source's collect, signal **only the python PID**, never the xargs wrapper shell (`/tmp/lac_collect2.sh <country>|<source>`). Killing the wrapper aborts the entire xargs queue. The `scripts/kill_collect_python.sh` helper does this correctly.
2. **`--rebuild` is destructive**: it opens `news.csv` with mode `"w"` and wipes existing data. NEVER use `--rebuild` during a refresh. Plain `po text collect --country X [--source Y]` only.
3. **Failure ledger persistence bug** (project_text_failure_ledger_bug): the ledger persists only on graceful run completion. Live-run failures from interrupted runs do NOT survive. This is exactly why **pre-seeding** is the only reliable way to get the scraper to permanently skip known-bad URLs.
4. **CLAUDE.md hard constraint** — never delete or modify files under `data/` directly via the agent. The ledger pre-seed is the one allowed mutation, and it's done by writing a script under `/tmp/` and invoking it via `poetry run python /tmp/seed_<source>_ledger.py`. The script is presented as the operator's hand, not a covert agent action.
5. **Resume runner pattern**: if xargs DOES abort despite rule 1 (e.g. the user killed something else, or a wrapper crashed), build a resume queue from the surviving DONE events and re-launch the remainder. See `references/orchestration.md` for the recipe.

## Output format

Two artifacts at end of run:

### 1. Persistent collect report

Always written by `scripts/render_collect_report.py` to:

```
outputs/text/reports/collect/collect_<region>_<ts>.md
```

A single markdown table mirroring the existing `outputs/text/reports/build/` format:

```
# Collect report — <region>
_Generated <ts>_

**Run:** region=<r> | parallelism=<P> | budget=<N>s | wall=<HHMMSS> | jobs=<done>/<total> completed

## Sources
| Country | Source | Status | Articles | Duration | Started (UTC) | Notes |
...

## Summary
- DONE: N | FAIL: N | BUDGET-KILLED: N | NOT-STARTED: N | wall: <dur>
- Slowest: <country>/<source> (<dur>)
- Fastest: <country>/<source> (<dur>)
```

Status values:
- `DONE` — exit 0 from `po text collect`
- `FAIL` — non-zero exit from `po text collect` (includes WAF-watchdog kills, which print `[STUCK]` first)
- `TIMEOUT-KILLED` — per-source wall-clock cap exceeded; runner killed the python
- `IN-FLIGHT` — START seen but no terminal event yet (only appears if you render the report before the run drained)
- `NOT-STARTED` — queued but xargs hadn't dispatched it yet

### 2. Inline chat report (operator-facing)

Still printed in chat after the run, for quick scan and operator-action callouts:

```
## Refresh: <region>
### <country> (N/M sources current)
- <source>: scraped <X> new articles | latest <date>
- <source>: SKIPPED — <reason>
- <source>: FIXED — <fix description>; <X> URLs ledger-seeded; <Y> new articles
- <source>: FAILED — <reason>; needs human attention
- <source>: DEFERRED — Cloudflare / rate-limit detected

## Pre-seeded ledgers (run these to apply locally):
- poetry run python /tmp/seed_<source_a>_ledger.py
- poetry run python /tmp/seed_<source_b>_ledger.py

## Total: N new articles across M sources | report: outputs/text/reports/collect/collect_<region>_<ts>.md
```

Group sources under their country header. Order countries alphabetically within the region. Pre-seeded ledger scripts are presented separately so the operator can review them before applying.

## Reference files

Read on demand — don't load upfront.

- `references/diagnose_loop.md` — stratified-probe code, classify rules, fix application, smoke-test verification
- `references/orchestration.md` — xargs runner template, monitor pattern, kill-python-only helper, resume-runner recipe
- `references/known_stuck_patterns.md` — the four canonical patterns with worked examples (cubanet, proceso, waterkant/el_estimulo, ciper_chile, dagblad_suriname)

## Quick start checklist

For region mode (primary path):

1. `bash .claude/skills/refresh-text-region/scripts/launch_refresh.sh <region> 8 300` — queue build + parallel launch with a 5-min per-source cap (no region-wide budget).
2. Arm Monitor on `/tmp/refresh_<region>_nohup.log` filtering for `^\[(START|DONE|FAIL|WARN|STUCK|TIMEOUT|REFRESH-DONE)`.
3. Periodically scan per-source logs for stuck signals; when found, apply the diagnose+fix loop.
4. When `[REFRESH-DONE]` arrives, run `poetry run python .claude/skills/refresh-text-region/scripts/render_collect_report.py <region> --parallelism 8 --max-source-seconds 300`.
5. Read the resulting `outputs/text/reports/collect/collect_<region>_<ts>.md`, then emit the inline chat report.

For single-source mode:

1. Locate the YAML at `src/text/configs/<region>/<subregion>/<country>/<source>.yaml`.
2. Run the diagnose+fix loop directly. No orchestrator needed.
3. Emit a single-source report.
