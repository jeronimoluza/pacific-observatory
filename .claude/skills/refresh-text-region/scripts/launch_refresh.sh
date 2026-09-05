#!/bin/bash
# Launch a parallel `po text collect` refresh.
#
# Usage: launch_refresh.sh <region> [parallelism] [max_source_seconds]
#
# Defaults: parallelism=8, max_source_seconds=300 (5min per source — not per region)
#
# Side effects:
#   - writes /tmp/refresh_<region>_jobs.txt    (queue)
#   - writes /tmp/refresh_<region>_nohup.log   (events stream)
#   - per-source logs at /tmp/refresh_<tag>.log
#
# Emits to the nohup log:
#   [REFRESH-START] @ <epoch>
#   [START] <tag> @ <epoch>
#   [DONE ] <tag> @ <epoch>
#   [FAIL ] <tag> (exit N) @ <epoch>
#   [STUCK]   <tag> @ <epoch>     ← WAF false-CLEAR watchdog kill
#   [TIMEOUT] <tag> @ <epoch>     ← per-source wall-clock cap exceeded
#   [REFRESH-DONE] @ <epoch>
#
# There is NO region-wide budget. The orchestrator runs until the queue
# drains. The per-source cap (MAX_SOURCE_SECONDS, passed via env to runner.sh)
# is what bounds individual sources.

set -u

REGION="${1:?usage: launch_refresh.sh <region> [parallelism] [max_source_seconds] [max_articles]}"
PARALLELISM="${2:-8}"
MAX_SOURCE_SECONDS="${3:-300}"
MAX_ARTICLES="${4:-${MAX_ARTICLES:-}}"

SKILL_DIR="$(cd "$(dirname "$0")" && pwd)"
RUNNER="$SKILL_DIR/runner.sh"
chmod +x "$RUNNER"

JOBS_FILE="/tmp/refresh_${REGION}_jobs.txt"
NOHUP_LOG="/tmp/refresh_${REGION}_nohup.log"

# Build the job queue: walk src/text/configs/<region>/<subregion>/<country>/*.yaml
# Always per-source — no whole-country grouping.
poetry run python - "$REGION" "$JOBS_FILE" <<'PY'
import sys
from pathlib import Path

region = sys.argv[1]
out = Path(sys.argv[2])
base = Path(f"src/text/configs/{region}")
if not base.exists():
    sys.exit(f"missing {base}")

jobs = []
for country_dir in sorted(p for p in base.glob("*/*") if p.is_dir() and not p.name.startswith("_")):
    country = country_dir.name
    sources = sorted(
        y.stem for y in country_dir.glob("*.yaml")
        if not y.stem.startswith("_0_") and not y.stem.startswith("_")
    )
    if not sources:
        continue
    for src in sources:
        jobs.append(f"{country}|{src}")

out.write_text("\n".join(jobs) + "\n")
print(f"queued {len(jobs)} jobs → {out}", file=sys.stderr)
PY

if [ ! -s "$JOBS_FILE" ]; then
  echo "no jobs queued for $REGION" >&2
  exit 1
fi

# Wipe prior nohup log
: > "$NOHUP_LOG"

MAX_SOURCE_SECONDS="$MAX_SOURCE_SECONDS" MAX_ARTICLES="$MAX_ARTICLES" nohup bash -c "
  echo '[REFRESH-START] @ '\$(date +%s) >> '$NOHUP_LOG'
  cat '$JOBS_FILE' | xargs -P $PARALLELISM -I JOB env MAX_SOURCE_SECONDS=$MAX_SOURCE_SECONDS MAX_ARTICLES='$MAX_ARTICLES' '$RUNNER' JOB >> '$NOHUP_LOG' 2>&1
  echo '[REFRESH-DONE] @ '\$(date +%s) >> '$NOHUP_LOG'
" > /dev/null 2>&1 &
disown

echo "launched: region=$REGION parallelism=$PARALLELISM max_source_seconds=${MAX_SOURCE_SECONDS}s max_articles=${MAX_ARTICLES:-unlimited}"
echo "events:   $NOHUP_LOG"
echo "queue:    $JOBS_FILE"
echo "queue size: $(wc -l < "$JOBS_FILE" | tr -d ' ')"
