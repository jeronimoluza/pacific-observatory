# Monday onboarding: turn the week's discovery finds into sources

You are the orchestrator of an attended session on a8, started by hand in
`~/po-worktrees/discovery-onboard` (branch `prices/discovery-onboard`). The nightly cron
(`nightly.sh`, 01:00 UTC) has been searching and triaging all week; your job is to onboard
what it found, lowest-coverage country first, with one Sonnet worker per country.

Shorthand used below, run from `src/`:

    po() { ~/venv/bin/python -c "import sys;sys.argv=['po','prices','discovery']+sys.argv[1:];from cli import main;main()" "$@"; }

## Before you start

1. Read the `onboard-price-sources` skill's `SKILL.md`, its "Orchestrator mode" section,
   and `references/phases/discover.md` § "Working from a supplied candidate list". Nothing
   else from `discover.md`: discovery is done.
2. `flock -n ~/po/logs/discovery/.lock true` must succeed. If it fails, the nightly job is
   still running: wait for it, because workers probing while ddgs searches share one IP.
3. `po candidates` prints the queue: countries with `verified` or `ambiguous` rows, lowest
   source count first. That order is the work order.

## Per country

1. `po candidates --country <c> > ~/scratch/onboard/<date>/<c>.tsv`.
2. Spawn one Sonnet worker (`model: sonnet`) with the worker brief below and the TSV path.
   Run as many workers in parallel as the session sustains; start with 4 and add more
   while none fails on usage or rate limits. Never two workers on one country.
3. When a worker reports back:
   - Record every verdict it gives: `po record verdict <c> <domain> <status> --reason "..."`,
     plus `--config <yaml path>` for `scaffolded`. You are the only writer to the store.
   - `git add -f` the files it lists (a bare `build/` in `.gitignore` swallows source dirs),
     one commit per country, `git push origin prices/discovery-onboard`. Never push
     anywhere else, never merge.

## Stop when

The queue is empty, or a usage limit stops new workers. Then print one table:
country | scaffolded | rejected | blocked | still ambiguous, and the commits pushed.

## Worker brief (paste into each worker, with the country and TSV path)

> You onboard price sources for **<country>** in `~/po-worktrees/discovery-onboard`, with
> the `onboard-price-sources` skill. The candidates are in **<tsv>**: discovery and a
> plain-request triage already happened. Read `SKILL.md`, then `probe.md`, then only the
> scaffold file your source needs, plus `classification.md`. Do not read `discover.md`.
>
> 1. `ambiguous` rows first: open `best_url` (at most 3 pages, robots.txt obeyed,
>    1 request/s) and decide `verified` or `rejected` with a one-line reason. News sites,
>    cost-of-living guides and currency converters are `rejected`.
> 2. Each `verified` row: de-duplicate against `src/prices/configs/**/*.yaml` (registrable
>    domain + path prefix), then probe → scaffold → test, as the skill says.
> 3. Write your probe-log shard as the skill says. Do not run git and do not write to the
>    discovery store; the orchestrator does both.
>
> Safety, no exceptions: no proxies, VPNs, Tor or IP rotation; never solve a CAPTCHA; a
> login wall or CAPTCHA is `blocked_hard`; a plain-request 403 may be retried with
> curl_cffi impersonation or Playwright at 1 request/s; never fetch Facebook, Instagram,
> WhatsApp or TikTok.
>
> Report one line per domain: `domain | status | reason | config path or - | files written`,
> where status is one of scaffolded, verified (probed, not scaffolded), rejected,
> blocked_plain, blocked_hard.
