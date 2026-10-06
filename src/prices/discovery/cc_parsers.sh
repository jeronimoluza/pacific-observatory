#!/usr/bin/env bash
# Tuesday CC parser stage: headless Claude writes archived parsers for the sources the Monday
# CC sweep flagged (cc/needs_parser.txt), then their saved misses are re-run and landed.
# cron: 0 4 * * 2  setsid nohup bash <this file> </dev/null >/dev/null 2>&1
# Waits for STATUS_cc (week of the preceding Monday) to finish; polls, never takes its lock.
# Status: ~/po/logs/weekly/<YYYY-Www>/STATUS_parsers; summary: cc_parsers_summary.md.
set -u
# cron has no login session: point systemd-run --user at the lingering user manager.
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}
TREE=/home/jeronimoluza/po-worktrees/discovery-onboard
CLAUDE=/home/jeronimoluza/.local/bin/claude
PY=/home/jeronimoluza/venv/bin/python
WEEK=$(date -u -d "yesterday" +%G-W%V)
OUT=/home/jeronimoluza/po/logs/weekly/$WEEK
mkdir -p "$OUT"
status() { echo "$(date -u +%FT%TZ) $*" | tee "$OUT/STATUS_parsers" >>"$OUT/events.log"; }

exec 6>"$OUT/.parsers.lock"
flock -n 6 || exit 0

status "WAITING for the CC sweep (STATUS_cc)"
for _ in $(seq 360); do
  grep -qE " (DONE|FAILED|BLOCKED)" "$OUT/STATUS_cc" 2>/dev/null && break
  sleep 300
done
if ! grep -q " DONE" "$OUT/STATUS_cc" 2>/dev/null; then
  status "BLOCKED CC sweep did not finish: $(cat "$OUT/STATUS_cc" 2>/dev/null)"
  exit 1
fi
if [ ! -s "$OUT/cc/needs_parser.txt" ]; then
  status "DONE no source needs a parser"
  exit 0
fi

cd "$TREE" || { status "BLOCKED no tree $TREE"; exit 1; }
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  status "BLOCKED $TREE has uncommitted changes"
  exit 1
fi
git pull -q --ff-only origin prices/discovery-onboard || { status "BLOCKED git pull failed"; exit 1; }

status "RUNNING headless parser stage on $(wc -l <"$OUT/cc/needs_parser.txt") sources"
PROMPT=$(sed "s|{{WEEK}}|$WEEK|g; s|{{OUT}}|$OUT|g" src/prices/discovery/cc_parsers_prompt.md)
timeout 10h "$CLAUDE" -p "$PROMPT" \
  --model opus \
  --permission-mode dontAsk \
  --allowedTools "Bash" "Read" "Write" "Edit" "Glob" "Grep" "Agent" "TodoWrite" \
  --disallowedTools "WebSearch" "WebFetch" "Bash(rm:*)" "Bash(git merge:*)" "Bash(git push --force:*)" \
    "Bash(git push -f:*)" "Bash(git rebase:*)" "Bash(git reset:*)" "Bash(*ddgs*)" "Bash(crontab:*)" \
  --output-format stream-json --verbose \
  >"$OUT/cc_parsers.jsonl" 2>"$OUT/cc_parsers.stderr"
RC=$?
if [ ! -s "$OUT/cc_parsers_summary.md" ]; then
  status "FAILED rc=$RC no summary written; see $OUT/cc_parsers.stderr and cc_parsers.jsonl"
  exit 1
fi
DIRTY=""
[ -n "$(git status --porcelain --untracked-files=no)" ] && DIRTY=" WARNING tree dirty: Monday onboarding will block"

if [ -s "$OUT/parsers_fixed.txt" ]; then
  status "RUNNING retry of saved misses for $(wc -l <"$OUT/parsers_fixed.txt") parsed sources"
  cd "$TREE/src" && env PO_CC_INDEX_DIR=/mnt/backup5tb/cc_index \
    systemd-run --user --scope -q -p MemoryMax=6G "$PY" -c \
    "import sys; sys.argv = ['po', 'prices', 'cc-weekly'] + sys.argv[1:]; from cli import main; main()" \
    --sources "$OUT/parsers_fixed.txt" --retry-misses "$OUT/cc/misses" \
    --reasons no_extract,selectors_noprice --data-root /home/jeronimoluza/po/data/prices \
    --work "$OUT/cc_parsers_retry" >"$OUT/cc_parsers_retry.log" 2>&1
  status "DONE rc=$RC $(tail -1 "$OUT/cc_parsers_retry.log")$DIRTY"
else
  status "DONE rc=$RC no parser committed; see $OUT/cc_parsers_summary.md$DIRTY"
fi
