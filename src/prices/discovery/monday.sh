#!/usr/bin/env bash
# Monday onboarding, started by the /weekly skill: headless Claude runs monday.md as orchestrator.
# Holds the discovery lock for the whole session, so the nightly search never overlaps it.
# Status: ~/po/logs/weekly/<YYYY-Www>/STATUS_onboard; transcript: onboard.jsonl; summary: onboard_summary.md.
set -u
TREE=/home/jeronimoluza/po-worktrees/discovery-onboard
CLAUDE=/home/jeronimoluza/.local/bin/claude
WEEK=${WEEK:-$(date -u +%G-W%V)}
OUT=/home/jeronimoluza/po/logs/weekly/$WEEK
mkdir -p "$OUT"
status() { echo "$(date -u +%FT%TZ) $*" | tee "$OUT/STATUS_onboard" >>"$OUT/events.log"; }
free_gb() { df -BG --output=avail / | tail -1 | tr -dc 0-9; }

exec 8>"$OUT/.onboard.lock"
flock -n 8 || exit 0
exec 9>/home/jeronimoluza/po/logs/discovery/.lock
flock -w 10800 9 || { status "BLOCKED discovery lock held for 3 h; onboarding not started"; exit 1; }
if [ "$(free_gb)" -lt 5 ]; then
  status "BLOCKED disk $(free_gb) GB free < 5 GB; onboarding not started"
  exit 1
fi

cd "$TREE" || { status "BLOCKED no tree $TREE"; exit 1; }
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  status "BLOCKED $TREE has uncommitted changes"
  exit 1
fi
git pull -q --ff-only origin prices/discovery-onboard || { status "BLOCKED git pull failed in $TREE"; exit 1; }

status "RUNNING headless onboarding @$(git rev-parse --short HEAD)"
PROMPT=$(sed "s|{{WEEK}}|$WEEK|g; s|{{OUT}}|$OUT|g" src/prices/discovery/monday_prompt.md)
timeout 14h "$CLAUDE" -p "$PROMPT" \
  --model opus \
  --permission-mode dontAsk \
  --allowedTools "Bash" "Read" "Write" "Edit" "Glob" "Grep" "Agent" "WebFetch" "Skill" "TodoWrite" \
  --disallowedTools "WebSearch" "Bash(rm:*)" "Bash(git merge:*)" "Bash(git push --force:*)" \
    "Bash(git push -f:*)" "Bash(git rebase:*)" "Bash(git reset:*)" "Bash(*ddgs*)" "Bash(crontab:*)" \
  --output-format stream-json --verbose \
  >"$OUT/onboard.jsonl" 2>"$OUT/onboard.stderr"
RC=$?
if [ -s "$OUT/onboard_summary.md" ]; then
  status "DONE rc=$RC summary $OUT/onboard_summary.md"
else
  status "FAILED rc=$RC no summary written; see $OUT/onboard.stderr and onboard.jsonl"
fi
