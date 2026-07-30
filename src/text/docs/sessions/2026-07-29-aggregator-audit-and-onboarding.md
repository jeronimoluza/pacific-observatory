# 2026-07-29 — Aggregator coverage audit + two onboarding rounds (110 new sources)

## Goal

Two connected asks:

1. **Audit** the `onboard-region-newspapers` aggregator lists (now 5-strong with
   GDELT added) against the live `src/text/configs/` tree, and report which
   regions/subregions/countries can still receive source onboarding — separating
   *live* from *deferred* from *pending*.
2. **Act on it**: dispatch parallel Sonnet agents to actually onboard the gaps —
   first GDELT + MENAAP, then a second sweep across all non-Western-Europe regions
   for untried aggregator sources.

## Status model (how live / deferred / pending are encoded)

Discovered and verified against `src/core/config.py`:

- **LIVE** — plain `<source>.yaml` (collected).
- **DEFERRED** — `_0_<source>.yaml` — a Tier-2 "scrapeable but needs custom code"
  stub, or a deprioritised full config. **Not collected**, because
  `config.py:181` skips any config whose relative path has a part
  `startswith("_")`.
- **PENDING** — an aggregator candidate host with no YAML of either kind yet.

Aggregator seed lists live at
`.claude/skills/onboard-region-newspapers/references/known_aggregators/<region>.md`
— five H3 sections per country: `w3newspapers`, `onlinenewspapers`,
`allyoucanread`, `abyznewslinks`, `gdelt`.

## The audit (215 topology countries)

Cross-referenced with a throwaway script
(`$CLAUDE_JOB_DIR/tmp/audit_aggregators.py`): walk configs → per-country
live/deferred counts; parse `regions.yaml` topology; parse each aggregator MD;
registrable-domain diff for "fresh" (untried) candidates.

Headline findings at session start:

| region | countries | live | deferred | 0-live |
|---|---|---|---|---|
| eap | 38 | 201 | 0 | 0 |
| eca | 59 | 538 | 196 | **29** |
| menaap | 22 | 70 | 11 | 0 |
| sar | 6 | 334 | 1 | 0 |
| ssa | 48 | 339 | 44 | 0 |
| lac | 42 | 890 | 35 | 0 |

Three buckets:

- **Biggest pending block — ECA/western_europe (29 countries, all zero-live).**
  The entire subregion has no config dirs at all (Germany 356 candidate hosts,
  Italy 330, Spain 292, France, UK…). *Excluded from onboarding this session
  per user instruction.*
- **Deferred backlog — 287 `_0_` stubs across 71 countries, 196 in ECA**
  (Caucasus / Central Asia / Balkans heavy). Already-triaged Tier-2 — a
  custom-code revisit, distinct from pending.
- **Headroom — 41 <3-live countries.** Outside Western Europe these are mostly
  EAP small markets where GDELT is the lever (HK, DPRK, Macao, Brunei, Pacific
  micro-states).

`SAR`, `MENAAP`, `LAC` had no zero-live countries; `EAP` had 10 <3-live small
markets.

## Round 1 — GDELT (non-WE headroom) + MENAAP expansion

5 Sonnet agents (2 GDELT clusters + 3 MENAAP subregions). Each: dedup by host vs
existing configs → hard local-only filter → `assess-newspaper-source` per
candidate → write Tier-0/1 YAML + `_0_` stubs for Tier-2 → probe
(`--max-pages 1 --max-articles 50`, ≤2 parallel). No `--rebuild`.

**Result: ~40 confirmed GREEN new sources** (all Tier-0 WP-API, probed 100/100,
spot-verified 100 rows of real data):

- Macao `jtm`; Brunei `the_scoop` + `biz_brunei`.
- MENAAP middle_east (15): Iraq/Jordan/Lebanon ×3, Syria/Yemen ×2, Israel,
  West Bank & Gaza.
- MENAAP gulf: Bahrain `bahrain_this_week`, Saudi `al_bilad` (+ Qatar ×3 / UAE ×3
  from a crashed partial run).
- MENAAP north_africa/AFG/PAK (20): Algeria/Egypt/Libya/Morocco/Tunisia ×3,
  Afghanistan ×2, Pakistan ×3.

GDELT was **low-yield in EAP** (CJK majors are JS-CMS; DPRK's GDELT list is
almost all *foreign* NK-watcher sites, correctly rejected) but the recall lever
for MENAAP local-language dailies. Pacific micro-states + Seychelles/Cabo Verde
yielded **0** working (bot-blocked / broken-date / non-local) — correctly not
fabricated.

**Data trap caught:** Kuwait `al_masila` — a WordPress feed recently hijacked to
serve black-hat SEO gambling spam across its newest posts. Correctly deferred
(`_0_al_masila.yaml`), not activated.

Round-1 configs were committed by a **concurrent process** (see caveat) as
`7a77aba6 feat(text): expand and refresh newspaper source configs across regions`
— our sources included and verified tracked.

## Round 2 — untried aggregator sources across all non-WE regions

6 Sonnet agents, deduping against the now-committed tree. Excluded SSA (the
concurrent process owns it) and western_europe (user instruction).

**Result: 70 new GREEN sources + 26 deferred stubs across 30 countries**,
committed as `d0e7a8f7`:

| cluster | new live | notes |
|---|---|---|
| EAP east_asia | 11 | China 3, Japan 2, S.Korea 3, Taiwan 3 — **Tier-1 HTML** (CJK majors non-WP) |
| EAP southeast_asia | 8 | Indonesia 1, Malaysia 2, Philippines 2, Thailand 1, Vietnam 2 — mostly front-page-only depth |
| ECA western_balkans + eastern_europe | 24 | Balkans WP ecosystem rich; Belarus 2, Moldova 3, Ukraine 1 |
| ECA central_asia + south_caucasus | 17 | Kazakhstan 3, Armenia 3, Azerbaijan 3, Georgia 2, Tajikistan 2, Turkmenistan 2, Uzbekistan 2 (Kyrgyz 0) |
| SAR south_asia | 7 | Bangladesh 2, Nepal 3, Sri Lanka 2 (Bhutan/Maldives 0) |
| LAC | 3 | Guyana's flagship dailies kaieteur/stabroek + Guatemala plaza_publica |

## Discoveries / gotchas (candidates for the living docs)

- **STALE DOC:** `onboard-region-newspapers/SKILL.md` shows `text collect … -y`,
  but the CLI has **no `-y` flag**; all agents had to strip it. Fix the skill.
- **Source-key convention:** auto-onboarded ECA sources use dotted
  `<domain>.<tld>.yaml` keys at scale (`gazeta.uz.yaml`, `agora.md.yaml`).
  `config.py` discovery only skips `_`-prefixed parts, so dotted stems are valid
  keys. **Do not "clean up" by stripping the TLD** — it desyncs from siblings.
  Language variants: `gazeta.uz_russian.yaml`, `kun.uz__english.yaml`.
- **CJK / SEA majors are Vue/Next SPAs** (Media Prima, Next.js) → Tier-3
  unscrapeable without a headless browser. Onboard the WP/HTML ones as Tier-1
  pagination instead. Arc Publishing (Chosun Ilbo, Nación CR) = JS-hydrated body,
  Tier-3.
- **WP custom post types:** when `/wp-json/wp/v2/posts` returns `[]`, check
  `/wp-json/wp/v2/types` for a custom REST base (Thailand `dailynews` uses a
  `news` type — common on Elementor builds).
- **`client_http.py` landmine:** a container selector starting with `.` goes to
  `find_all(class_=expr[1:])`, which **breaks on dot-chained multi-class
  selectors** (`.item-row.item-row-2`). Use a single class.
- **`?page=N` no-op** is common on JP/KR/TW/LK sites (same class as the Eswatini
  `?paged=` quirk) — mitigate with `max_pages: null` or a `follow_link`
  single-page pattern. And a `/section/trang-{n}.html` URL can serve distinct
  IDs yet be a stale mis-categorised archive (sggp.vn) — verify by reading
  scraped **titles/dates**, not URL shape.
- **RSS gap:** Maldives outlets (sun.mv, thepress.mv) publish only via RSS; the
  pipeline has no RSS listing strategy (api / pagination / archive / sitemap /
  cursor only) — a feature gap blocking that market.

## Concurrency caveat (important for resume)

This main checkout was being **written by a parallel process** throughout the
session (it committed `7a77aba6`, actively onboarding SSA + extra MENAAP/SSA
configs). Consequences:

- The raw `git status` untracked count (210 at one point) conflates our work with
  the parallel job's. Attribution was done via **agent reports + the job-start
  audit baseline**, not blanket counts.
- **Never `git add -A` here** — scope commits to explicit paths/regions.
- Our round-2 commit `d0e7a8f7` was scoped to the untracked yaml in our 6 regions
  (eap/eca/sar/lac) only — verified nothing outside those regions was swept in.

## Commit / environment notes

- Branch `template-repo` (not `main`). **Nothing pushed.**
- Commits here need the `.venv`-on-PATH prefix (sibling-repo pre-commit hook
  needs ruff/pre-commit on PATH):
  `export PATH="$(git rev-parse --show-toplevel)/.venv/bin:$PATH" && git commit …`
- Commit messages carry **no `Co-Authored-By: Claude`** trailer (user rule).

## Deviations

- The balkans/EE agent ran `--rebuild` once on the brand-new `moldova/infomarket`
  (against the no-rebuild instruction) to force a re-scrape after a selector fix —
  harmless, no pre-existing data at risk.

## Backlog / next steps

- **ECA/western_europe** (29 zero-live countries) is the remaining big untouched
  block — the natural next onboarding target.
- **Deep backfill (`--rebuild`)** the ~110 new sources (round 1 + round 2) when
  ready; they are config-only (probed, not backfilled). SEA sources are
  front-page-only → thin history.
- **Fix `-y`** in `onboard-region-newspapers/SKILL.md`.
- Consider folding the recurring gotchas above into
  `references/known_quirks.md` and a pipeline RSS listing strategy for Maldives.
- Optionally `git push` `d0e7a8f7`.
