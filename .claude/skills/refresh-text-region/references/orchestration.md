# Orchestration

Patterns for running parallel `po text collect` jobs, monitoring them, killing them safely, and recovering when xargs misbehaves.

## Build the job queue

For region/subregion mode, walk the configs directory and build `country|source` lines:

```python
from pathlib import Path
import re, yaml

def build_queue(region: str, subregion: str | None = None) -> list[str]:
    """Return list of 'country|source' lines for the queue.

    Empty source means 'whole country' (run --country X).
    Per-source split when a country has >4 sources, so a single slow source
    doesn't block the rest of the country.
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
        if len(sources) <= 4:
            jobs.append(f"{country}|")
        else:
            for src in sources:
                jobs.append(f"{country}|{src}")
    return jobs
```

The split-when-many heuristic prevents the cubanet-style stuck source from holding up the other 5 cuba sources for hours.

## The runner script

Save as `/tmp/refresh_<region>_runner.sh` (chmod +x):

```bash
#!/bin/bash
# Args: <country>|<source>  (source may be empty)
JOB="$1"
COUNTRY="${JOB%|*}"
SOURCE="${JOB#*|}"

if [ -n "$SOURCE" ]; then
  TAG="${COUNTRY}__${SOURCE}"
  ARGS="--country $COUNTRY --source $SOURCE"
else
  TAG="$COUNTRY"
  ARGS="--country $COUNTRY"
fi

echo "[START] $TAG"
poetry run po text collect $ARGS > "/tmp/refresh_${TAG}.log" 2>&1
STATUS=$?
if [ $STATUS -eq 0 ]; then
  echo "[DONE ] $TAG"
else
  echo "[FAIL ] $TAG (exit $STATUS)"
  tail -3 "/tmp/refresh_${TAG}.log"
fi
```

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
  command: tail -F /tmp/refresh_<region>_nohup.log | grep -E --line-buffered "^\[(START|DONE|FAIL|REFRESH-DONE)"
```

Each event becomes a notification. When `[REFRESH-DONE]` arrives, the queue is fully drained.

## Detecting stuck sources mid-run

Periodically (every 5-10 minutes during a long refresh) scan each per-source log for the warning:

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
