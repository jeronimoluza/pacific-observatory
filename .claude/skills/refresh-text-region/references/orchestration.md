# Orchestration

Patterns for running parallel `po text collect` jobs, monitoring them, killing them safely, and recovering when xargs misbehaves.

**Primary path** (use these — added 2026-06-08, timestamped events + hard budget cutoff baked in):

- `scripts/launch_refresh.sh <region> [P=8] [budget_s=300]` — builds queue, launches runner, arms budget watchdog
- `scripts/runner.sh` — permanent per-source runner (same WAF watchdog as the template below; emits `[START]/[DONE]/[FAIL]` with epoch timestamps)
- `scripts/render_collect_report.py <region> --parallelism P --budget S` — renders `outputs/text/reports/collect/collect_<region>_<ts>.md`

The remainder of this file documents the underlying patterns (still useful for ad-hoc per-source re-fires, resume after xargs abort, and manual tweaks).

## Build the job queue

For region/subregion mode, walk the configs directory and build `country|source` lines:

```python
from pathlib import Path
import re, yaml

def build_queue(region: str, subregion: str | None = None) -> list[str]:
    """Return list of 'country|source' lines for the queue.

    Always per-source — never group a whole country into one xargs slot.
    A hard time budget would otherwise unfairly starve the late entries in
    a group if the first source in that group is slow.
    """
    base = Path(f"src/text/configs/{region}")
    if subregion:
        base = base / subregion
    jobs = []
    for country_dir in sorted(p for p in base.glob("*/*") if p.is_dir() and not p.name.startswith("_")):
        country = country_dir.name
        sources = sorted(
            y.stem for y in country_dir.glob("*.yaml")
            if not y.stem.startswith("_0_") and not y.stem.startswith("_")
        )
        for src in sources:
            jobs.append(f"{country}|{src}")
    return jobs
```

Per-source queueing ensures the `-P` slots are filled with independent units of work, so a single slow source (cubanet-style) only burns one slot — and the budget cutoff applies fairly to every source.

## The runner script

Save as `/tmp/refresh_<region>_runner.sh` (chmod +x). The body bakes in a
false-CLEAR WAF watchdog: when the scraper emits the `selectors may be broken`
warning AND the target `news.csv` shows zero size growth for `STALL_SECONDS`
afterwards, the watchdog SIGTERMs the python child and emits `[STUCK]` so
operators don't have to poll per-source logs to catch silent stalls
(report.az / 24sata / svaboda / investor pattern — ~4h of wasted compute each
before this was added).

```bash
#!/bin/bash
# Args: <country>|<source>  (source may be empty)
#
# Env knobs:
#   STALL_SECONDS    — seconds of post-warning zero-growth before killing (default 300)
#   POLL_SECONDS     — sampling cadence (default 60)
#   DATA_BASE        — root for news.csv resolution (default $(pwd)/data/text)
#   KILL_SCRIPT      — kill_collect_python.sh helper path
#   DISABLE_WATCHDOG=1 — bypass the watchdog (legacy plain-wrap behaviour)
JOB="$1"
COUNTRY="${JOB%|*}"
SOURCE="${JOB#*|}"

if [ -n "$SOURCE" ]; then
  TAG="${COUNTRY}__${SOURCE}"
  ARGS=(--country "$COUNTRY" --source "$SOURCE")
else
  TAG="$COUNTRY"
  ARGS=(--country "$COUNTRY")
fi

LOG="/tmp/refresh_${TAG}.log"
echo "[START] $TAG"

if [ "${DISABLE_WATCHDOG:-0}" = "1" ]; then
  poetry run po text collect "${ARGS[@]}" > "$LOG" 2>&1
  STATUS=$?
  if [ $STATUS -eq 0 ]; then
    echo "[DONE ] $TAG"
  else
    echo "[FAIL ] $TAG (exit $STATUS)"
    tail -3 "$LOG"
  fi
  exit $STATUS
fi

STALL_SECONDS="${STALL_SECONDS:-300}"
POLL_SECONDS="${POLL_SECONDS:-60}"
DATA_BASE="${DATA_BASE:-$(pwd)/data/text}"
KILL_SCRIPT="${KILL_SCRIPT:-$(pwd)/.claude/skills/refresh-text-region/scripts/kill_collect_python.sh}"
WARNING_RE="after [0-9]+ article attempts, 0 were successfully scraped"

if [ -n "$SOURCE" ]; then
  FIND_PATTERN="*/${COUNTRY}/${SOURCE}/news.csv"
else
  FIND_PATTERN="*/${COUNTRY}/*/news.csv"
fi

csv_size() {
  local total=0 f sz
  while IFS= read -r f; do
    [ -f "$f" ] || continue
    sz=$(stat -f%z "$f" 2>/dev/null || stat -c%s "$f" 2>/dev/null || echo 0)
    total=$(( total + sz ))
  done < <(find "$DATA_BASE" -path "$FIND_PATTERN" 2>/dev/null)
  echo "$total"
}

poetry run po text collect "${ARGS[@]}" > "$LOG" 2>&1 &
WRAP_PID=$!

last_size=$(csv_size)
last_growth_at=$(date +%s)
warning_seen_at=""
stuck_triggered=0

while kill -0 "$WRAP_PID" 2>/dev/null; do
  sleep "$POLL_SECONDS"
  cur_size=$(csv_size)
  if [ "$cur_size" != "$last_size" ]; then
    last_size="$cur_size"
    last_growth_at=$(date +%s)
  fi
  if [ -z "$warning_seen_at" ] && grep -Eq "$WARNING_RE" "$LOG" 2>/dev/null; then
    warning_seen_at=$(date +%s)
    echo "[WARN ] $TAG (selector-broken warning fired; arming watchdog ${STALL_SECONDS}s)"
  fi
  if [ -n "$warning_seen_at" ]; then
    since_growth=$(( $(date +%s) - last_growth_at ))
    if [ "$since_growth" -ge "$STALL_SECONDS" ]; then
      echo "[STUCK] $TAG (no news.csv growth for ${since_growth}s after warning; killing python)"
      if [ -x "$KILL_SCRIPT" ]; then
        "$KILL_SCRIPT" "$COUNTRY" "$SOURCE" >&2 || true
      else
        if [ -n "$SOURCE" ]; then
          PIDS=$(ps aux | grep -F "po text collect --country $COUNTRY --source $SOURCE" | grep -v grep | grep "/.venv/bin/" | awk '{print $2}')
        else
          PIDS=$(ps aux | grep -F "po text collect --country $COUNTRY" | grep -v -- "--source" | grep -v grep | grep "/.venv/bin/" | awk '{print $2}')
        fi
        for PID in $PIDS; do kill -TERM "$PID" 2>/dev/null || true; done
      fi
      stuck_triggered=1
      break
    fi
  fi
done

wait "$WRAP_PID" 2>/dev/null
STATUS=$?

if [ "$stuck_triggered" -eq 1 ]; then
  echo "[FAIL ] $TAG (WAF-watchdog killed; suspected false-CLEAR — DEFER)"
  tail -3 "$LOG"
elif [ $STATUS -eq 0 ]; then
  echo "[DONE ] $TAG"
else
  echo "[FAIL ] $TAG (exit $STATUS)"
  tail -3 "$LOG"
fi
```

### Watchdog semantics

- **Triggers** on the composite signature: `⚠ selectors may be broken`
  warning emitted AND the target `news.csv` has not grown by even one byte
  for `STALL_SECONDS` since the last growth measurement.
- **Does not** rely on the warning alone — cubanet / proceso / dagblad
  legitimately fire the warning while scraping new articles, so the
  zero-growth co-requirement keeps them safe.
- **Does not** rely on tqdm rate — false-CLEAR sources self-report 5+ it/s
  while persisting zero rows.
- After a kill, the wrapper emits `[FAIL ] <tag> (WAF-watchdog killed; suspected
  false-CLEAR — DEFER)` so the source can be triaged out-of-band; xargs sees
  a clean child exit and moves to the next job.
- Tune `STALL_SECONDS` per region: 300s (5min) is a safe default; raise to
  600s for slow-rate-limited sources (sitemap-heavy backfills) and lower to
  120s for fast-iteration archive/pagination sources where any 2-minute
  stall is unphysical.

## Launch detached

```bash
chmod +x /tmp/refresh_<region>_runner.sh
nohup bash -c '
  cat /tmp/refresh_<region>_jobs.txt | xargs -P 4 -I JOB /tmp/refresh_<region>_runner.sh JOB
  echo "[REFRESH-DONE]"
' > /tmp/refresh_<region>_nohup.log 2>&1 &
disown
```

The `[REFRESH-DONE]` sentinel at the end lets the monitor know the queue is exhausted (vs xargs aborting).

## Monitor pattern

```
Monitor:
  description: refresh <region> — START/DONE/FAIL events
  timeout_ms: 3600000
  persistent: false
  command: tail -F /tmp/refresh_<region>_nohup.log | grep -E --line-buffered "^\[(START|DONE|FAIL|WARN|STUCK|REFRESH-DONE)"
```

Each event becomes a notification. When `[REFRESH-DONE]` arrives, the queue is fully drained.

Event semantics:

- `[START]` / `[DONE ]` / `[FAIL ]` / `[REFRESH-DONE]` — normal queue lifecycle.
- `[WARN ]` — the runner's watchdog has been armed because the per-source log
  emitted the `selectors may be broken` warning; no action needed yet.
- `[STUCK]` — the watchdog has just killed the python child because the source
  matched the false-CLEAR signature (warning + zero `news.csv` growth for
  `STALL_SECONDS`). Followed by a `[FAIL ]` line with a `WAF-watchdog killed`
  tail. These should be triaged immediately: probe the source, decide if it's
  Pattern 1 (pre-seed) or Pattern 3 (DEFER), then re-fire if appropriate.

## Detecting stuck sources mid-run

The watchdog inside the runner now auto-emits `[STUCK]` events for the
false-CLEAR / WAF signature, so manual polling is mostly a backup for cases
the watchdog misses (e.g. discovery-phase hangs that never reach the warning).
Run these only if `[STUCK]` events aren't showing up but you suspect a stall:

```bash
for log in /tmp/refresh_*__*.log /tmp/refresh_*.log; do
  [ -f "$log" ] || continue
  if grep -q "after [0-9]\+ article attempts, 0 were successfully scraped" "$log"; then
    echo "STUCK: $log"
  fi
done
```

For iter-rate detection (slower sources where the warning hasn't fired yet):

```bash
# Extract last tqdm bar; report sources with current rate > 5s/it
for log in /tmp/refresh_*__*.log /tmp/refresh_*.log; do
  [ -f "$log" ] || continue
  rate=$(tr '\r' '\n' < "$log" | grep -oE '[0-9]+\.[0-9]+s/it' | tail -1)
  if [ -n "$rate" ]; then
    val=$(echo "$rate" | sed 's/s\/it//')
    if (( $(echo "$val > 5.0" | bc -l) )); then
      echo "SLOW ($rate): $log"
    fi
  fi
done
```

## Kill a stuck collect — python only, NOT the wrapper

This is the lesson from 2026-05-04. Use `scripts/kill_collect_python.sh`:

```bash
./scripts/kill_collect_python.sh <country> <source>
```

The script finds processes matching `po text collect --country X --source Y` and SIGTERMs the python PID directly. The bash wrapper around it (`/tmp/refresh_<region>_runner.sh`) is left alone, so it can emit a clean `[FAIL ] <tag> (exit 143)` and xargs picks up the next job.

**Never** run `pkill bash` or `kill <wrapper-pid>` — it will SIGTERM-cascade and abort the queue.

## Resume runner — when xargs aborts despite our care

If xargs aborts (visible as `xargs: ...: terminated with signal 15; aborting` in the nohup log), build a resume queue from the surviving DONE events and re-launch:

```python
done = set()
with open("/tmp/refresh_<region>_nohup.log") as f:
    for line in f:
        if line.startswith("[DONE"):
            done.add(line.split("]", 1)[1].strip())

remaining = []
with open("/tmp/refresh_<region>_jobs.txt") as f:
    for line in f:
        line = line.strip()
        if not line: continue
        country, source = line.split("|", 1)
        tag = f"{country}__{source}" if source else country
        if tag in done: continue
        remaining.append(line)

with open("/tmp/refresh_<region>_jobs_resume.txt", "w") as f:
    for r in remaining:
        f.write(r + "\n")
```

Then launch the resume runner the same way:

```bash
nohup bash -c '
  cat /tmp/refresh_<region>_jobs_resume.txt | xargs -P 4 -I JOB /tmp/refresh_<region>_runner.sh JOB
  echo "[REFRESH-RESUME-DONE]"
' > /tmp/refresh_<region>_resume_nohup.log 2>&1 &
disown
```

Arm a fresh Monitor on the resume nohup log.

## Single-source re-fire after fix

When a stuck source has been fixed and we want it to complete alongside the rest of the run:

```bash
nohup bash -c '
  echo "[REFIRE-START] '$COUNTRY'/'$SOURCE'"
  poetry run po text collect --country '$COUNTRY' --source '$SOURCE' > /tmp/refresh_'${COUNTRY}__${SOURCE}'.log 2>&1
  ST=$?
  if [ $ST -eq 0 ]; then echo "[REFIRE-DONE ] '$COUNTRY'/'$SOURCE'"; else echo "[REFIRE-FAIL ] '$COUNTRY'/'$SOURCE' (exit '$ST')"; fi
' > /tmp/refresh_refire_${SOURCE}.log 2>&1 &
disown
```

Track refire jobs in the same report under their country header.
