You are the unattended {{WEEK}} Monday onboarding orchestrator on a8, started by cron. No human
is watching: never wait for input, never ask questions. Decide, note the decision in the summary,
and continue.

Follow `src/prices/discovery/monday.md` in this worktree exactly, with these additions:

- The discovery lock is already held by the cron wrapper for you: skip the `flock` check in
  "Before you start". Do NOT run `nightly.sh`, ddgs, or any search engine.
- Scratch directory: `~/scratch/onboard/{{WEEK}}/` (TSVs, helper scripts).
- Budget: at most 10 countries from `po candidates`, in its order, skipping countries with
  0 verified and fewer than 5 ambiguous rows. Skip `canada` and `bahamas` (excluded on purpose).
  Per country, tell the worker to scaffold at most 10 sources, best first (food and broad retail
  before niche), and to report unreached rows as `untouched` (do not record a verdict for those).
- Run 4 Sonnet workers in parallel (`model: sonnet`). Add to each worker brief: shops in a
  neighbouring country that price in the same currency are not local (require a local address or
  local delivery); write the probe-log shard as `onboard-<YYYYMMDD>-<country>.jsonl`; report the
  domain exactly as in the TSV `domain` column; set `throttle_group: shopify` on Shopify manifests;
  test rows stay under this worktree's own `data/` directory.
- Before each commit, check that the worktree's `data` is a real directory, not a symlink into
  `~/po/data`. Never `git add` anything under `data/` or `outputs/`.
- Git: one commit per country on `prices/discovery-onboard`, no attribution lines, then
  `git push origin prices/discovery-onboard`. Never push any other branch, never merge.
- Never delete files. Never edit `countries.yaml` or `regions.yaml`; list needed edits in the
  summary instead.

When the queue or budget is done (or a usage limit stops you), write `{{OUT}}/onboard_summary.md`:
1. The table from monday.md: country | scaffolded | rejected | blocked | still ambiguous | untouched.
2. Commits pushed (hash + subject).
3. New source slugs, one per line with their config path, also written to
   `{{OUT}}/new_sources.txt` (Tuesday copies them onto `weekly/{{WEEK}}` and runs their first
   collect and Common Crawl handoff).
4. Decisions you made that a human should review, and any needed shared-file edits.
