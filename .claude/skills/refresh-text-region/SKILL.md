---
name: refresh-text-region
description: "Refresh a text region end to end on the Mac (SSKJL mounted): pull a8 staged collect runs, merge, build, run the policy step (corpus pass + websearch for fuel and food trackers), publish. Trigger on 'update text data for sar', 'refresh lac text', 'run po text update for menaap', 'fix text source <name>', 'why is <source> at low %'. One or more regions per invocation. Also diagnoses and fixes stuck sources (broken selectors, excerpt-only articles, ledger pre-seeds). Two modes: region refresh, or single-source fix."
---

# Refresh Text Region

Runs `po text` for one or more regions from staged collect to published dashboards, on the Mac, because only the Mac has SSKJL. Collect never writes to SSKJL: it writes deltas to a staging dir, and `po text merge` is the single SSKJL writer.

Regions: `eap | eca | menaap | sar | lac | ssa`. Sources must already be onboarded in `src/text/configs/<region>/`; for a fresh region use `onboard-region-newspapers`.

Hard rules:
- Print every `rm`; the user runs it.
- Run `po text collect` and `po text build` without `--rebuild` (collect's `--rebuild` wipes `news.csv`).
- Kill the python PID only (`scripts/kill_collect_python.sh <source>`); killing the xargs wrapper aborts the whole queue.
- Say which machine each number came from (a8 STATUS vs Mac).
- Ledger pre-seeds are scripts under `/tmp/` that the operator runs; the agent does not edit `data/` itself.

Single-source fix mode ("fix text source X"): go to `references/diagnose_loop.md`, then smoke-test. On the Mac with SSKJL mounted, test with a direct single-source run (`po text collect --country X --source Y --max-articles 5`); otherwise test with `--staging <dir>`.

## Flow

Finish each step for all regions before the next. A step is done when its check holds.

### 0. Preflight
- `ls /Volumes` lists `SSKJL`.
- `data/text/<r>` resolves for every region (`ls data/text/<r>/ | head -1`).
- `ssh a8 true` succeeds.
Any miss: stop and name it.

### 1. Get staged runs
a8 collects Mon and Fri 06:00 UTC into `~/text_staging/<run_id>/` (`references/a8_side.md`).

```bash
rsync -rt --exclude .lock a8:~/text_staging/ ~/text_staging/
```

Unmerged run = a dir in `~/text_staging/` with a `.done` file and no `<region>/.merged` (`po text merge --region <r>` takes exactly those; it skips runs without `.done`, which a8 may still be writing). Print each unmerged run's `STATUS.md`. Done when every one is shown. A STATUS showing `ABORTED` (disk below floor, disk errors): refuse to merge that run and ask the user.

No a8 run, or the user wants fresh data now: collect on the Mac, still staged.

```bash
STAGING=~/text_staging/<run_id> bash .claude/skills/refresh-text-region/scripts/launch_refresh.sh <r> 12 300
```

`<run_id>` = `date -u +%Y%m%dT%H%MZ`. Parallelism: `launch_refresh.sh` defaults to 8; Mac uses 12, a8 uses 24. Per-source cap 300 s, no region-wide budget. Monitor `/tmp/refresh_<r>_nohup.log` for `^\[(START|DONE|FAIL|WARN|STUCK|TIMEOUT|REFRESH-DONE)`. Stuck sources: see below. After `[REFRESH-DONE]`, write a `STATUS.md` in the run dir from the events log so it matches a8 runs, `touch ~/text_staging/<run_id>/.done` (merge skips runs without it), and render the collect report (`references/orchestration.md`).

### 2. Merge
```bash
poetry run po text merge --region <r>
```
Takes all unmerged runs, oldest first. Exit 1 = a source failed verification: stop and report it; no build.

Push the ledger (Mac is master) and keep the SSKJL copy:
```bash
rsync -t ~/text_state/<r>.sqlite a8:~/text_state/
cp ~/text_state/<r>.sqlite /Volumes/SSKJL/text_state/
```
Print, never run, the cleanup for each merged run on both hosts:
```
rm -rf ~/text_staging/<run_id>
ssh a8 'rm -rf ~/text_staging/<run_id>'
```
Merge does not delete staging, so the run dirs still exist for step 4 until the user runs these. Keep the merged run ids.

### 3. Build
```bash
poetry run po text build --region <r> --max-parallel-sources 8
```

### 4. Policy step
Details: `references/policy_step.md`. The orchestrator (this session) dispatches in one message one Sonnet subagent per region x tracker (fuel, food): 12 for six regions. Each agent runs (a) the corpus pass over this refresh's new articles (the merged runs' staged `news.csv` via `--data-root`), then (b) WebSearch research for what the corpus missed. Research rules and workbook schema live in `update-fuel-crisis-policy` and `update-food-security-policy`; do not restate them. The WebSearch cap is session-wide (about 200): give each agent a budget (200 / agent count, 16 for 12 agents) in its prompt.

Done when every agent has returned its one-line result and each tracker workbook has today's dated edition.

### 5. Addons and publish
Per region:
```bash
poetry run po text build-policy-addons --region <r>
poetry run po text build-policy-addons --region <r> --tracker food
poetry run po text publish --region <r>
poetry run po text publish --region <r> --tracker food --skip-database-status
```
Fuel publish refreshes database status; food skips it, so each region skips once. `publish` exits 1 when an addon is missing: stop and report.

### 6. Review summary
Write `outputs/text/reports/refresh/refresh_<r>_<date>.md`: new policy rows from this refresh, split by provenance (`corpus` vs `websearch`), each with country, measure, date, source URL (from the new workbook editions' Provenance column and the agents' returns). Show it in chat so the user can review after publish.

Print, never run, the backup (no automatic backup):
```
rsync -rt --exclude '._*' /Volumes/SSKJL/data/text/ /Volumes/BACKUP5TB/sskjl-20260928/data/text/
```
(the 2026-09-28 SSKJL backup tree; resumable).

Final chat report per region: sources current/stuck/deferred, merged runs, new news rows, new policy rows by provenance, report path.

## Stuck sources

Stuck = any of: log line `after N article attempts, 0 were successfully scraped`; tqdm above 5 s/it for 50+ iterations; runner `[STUCK]` (watchdog kill after `STALL_SECONDS` without `news.csv` growth). `po text status` alone is no signal; a quiet site shows "2d ago". Follow `references/diagnose_loop.md`: kill python only, probe, classify into `references/known_stuck_patterns.md`, fix, smoke-test, re-queue the source as its own detached job. Green = `Articles Scraped > 0`, or `Skipped (ledger)` matches the seeded count. Cloudflare/rate-limit: mark DEFERRED, no auto-fix. For a8 runs the same signals are in `events_<r>.log` in the run dir.

## Reference files (read on demand)

- `references/policy_step.md`: step 4 commands, agent inputs, provenance, search budget
- `references/a8_side.md`: a8 timer, ledgers, first-time setup
- `references/orchestration.md`: runner template, monitor pattern, watchdog, resume recipe, collect report
- `references/diagnose_loop.md`, `references/known_stuck_patterns.md`: stuck-source repair
