---
name: onboard-region-newspapers
description: "Batch-onboard newspaper text-scraper sources for the Pacific Observatory pipeline given a region, subregion, or list of countries. Use this when the user asks to 'add newspapers for <region>', 'scrape <subregion>', 'start scraping <country list>', references src/configs/regions.yaml or src/text/configs/, or wants to expand text coverage across multiple countries. Orchestrates discovery → config writing → probe → background rebuilds, applying the category filter rule (national → economy/politics → latest) and the regional-aggregator fallback (a region-appropriate cross-country aggregator with localized per-country sections, if one exists). Trigger this whenever 2+ countries are involved — for single-URL assessment, fall back to the assess-newspaper-source skill."
---

# Onboard Region Newspapers

Batch-onboard newspaper text-scraper sources for one region/subregion (or an explicit country list) of the Pacific Observatory pipeline. The deliverable per country is up to 3 newspaper YAMLs at `src/text/configs/<region>/<subregion>/<country>/`, probed and (if probes look healthy) running a full `--rebuild` in the background.

## When to use this skill

- The user provides a **set** of countries — a region (`eap`, `eca`, `menaap`, `ssa`), a subregion (`southern_africa`, `east_africa`), or an explicit list (`["ghana", "nigeria", "senegal"]`).
- They want each country to end up with ~3 working scraper configs and start backfilling.
- For a **single URL** assessment, prefer the `assess-newspaper-source` skill — it does deeper per-site triage. This skill calls `assess-newspaper-source` per candidate where deeper inspection is warranted.

## Repo entry points

- Country topology: `src/configs/regions.yaml`, `src/configs/countries.yaml`
- Scraper configs: `src/text/configs/<region>/<subregion>/<country>/<source>.yaml`
- CLI: `python run.py text collect --source <key> [--max-pages N] [--max-articles N] [--rebuild] [-y]`
- Pre-existing examples to mirror: `src/text/configs/menaap/middle_east/lebanon/naharnet.yaml` (HTML pagination), any `wp-json` config under `src/text/configs/eap/`.
- Cleaning functions registry: `src/text/scrapers/pipelines/cleaning/__init__.py`

## Workflow (per region/subregion or country list)

### 1. Resolve country list and language hints

Read `src/configs/regions.yaml` to expand the user's input into concrete country slugs. Read `src/configs/countries.yaml` to learn each country's `languages:` list. The `languages:` list is what tells you whether you should look for local-language papers (e.g. `[en, fr]`, `[en, portuguese]`, `[en, afrikaans]`).

For each country, aim for **3 sources**, ideally **2 local-language + 1 English**. If the country only has `[en]`, all 3 will be English. If a local-language source can't be found that's working, accept the imbalance and move on — don't force a Tier 3.

### 2. Discover candidate newspapers (per country, sequential)

Process countries one at a time. For each country, build a candidate list (~5-8 URLs), then run each candidate through `/assess-newspaper-source` and probe Tier 0/1 results — this yields the highest-quality scrapers.

**2a. Static aggregator harvest (mandatory first step).** Read `references/known_aggregators/<region>.md` and locate the `## <country_slug>` block (each region file is structured by H2 sections per country, with five H3 sub-sections — one per aggregator — listing pre-extracted outlets).

The five aggregators covered are `w3newspapers`, `onlinenewspapers`, `allyoucanread`, `abyznewslinks`, and `gdelt`. The ignore rules (Wikipedia, BBC profiles, CIA Factbook, wire hubs, social platforms, aggregator self-links) were already applied at population time — see `references/known_aggregators/README.md` for the full ruleset and refresh instructions. **Do not** re-fetch the aggregator homepages live; the static reference replaces that step.

The `gdelt` section is different from the other four: entries are **bare domains ranked by GDELT monitoring volume** (top of the list = genuine national outlets; the tail is noisier — government, tourism, airline, party sites survive), with no curated outlet name. Its value is recall of real local outlets the curated four miss (especially small Pacific markets). Apply the local-only filter (below) and the `/assess-newspaper-source` gate **harder** to `gdelt` candidates, and prefer the top few by volume.

If the country's H2 block is missing entirely, or every aggregator H3 reads `(no entries)`, treat the static reference as exhausted for this country and skip straight to step 2c (WebSearch fallback) below.

Otherwise, collect all `<outlet name> — <outlet url>` bullet lines under the four aggregator H3s, dedupe by host, and apply the **local-only filter** below. Then layer in any obvious local outlet from prior knowledge that the aggregators missed.

**Local-only filter (hard rule).** Keep only outlets that are *of* the country. Reject:
- Foreign outlets covering the country (e.g. BBC News' Congo desk, Reuters Africa, AFP, France 24, RFI, Al Jazeera, VOA, DW, CNN, Bloomberg country pages). These produce off-country editorial framing and pollute the EPU index. (Most are pre-filtered by the populator, but new ones leak through occasionally.)
- Country *profiles* / encyclopedic reference pages (CIA World Factbook entries, Wikipedia mirrors, "about Congo" pages). Not news.
- Diaspora-edited sites whose editorial home is in another country, unless they are the de-facto national outlet (rare — confirm via masthead/about page).
- Wire-service mirrors and aggregator landing pages that don't publish original local content.
- Sports / lifestyle / entertainment outlets that survive aggregator listings but don't carry national news.

A useful sanity check: the outlet's masthead, About page, or domain registration should place it in-country, and the front page should carry national news (politics, economy, local events) written for a domestic audience.

If a known_aggregator entry's URL is dead or the site has clearly migrated, drop it. The static reference can drift between refreshes — when in doubt, follow the live site.

**2c. WebSearch fallback (when the static reference is exhausted).**

If the country has no entries in `known_aggregators/<region>.md`, OR every static-reference candidate has already been onboarded / deferred and the country still has fewer than 3 working sources, escalate:

1. Run `WebSearch` with each of:
   - `"<country display name> local newspapers"`
   - `"<country display name> newspapers in english"`
   - For each non-English language listed in `countries.yaml` `languages:`, `"<country display name> newspapers in <language>"`
2. Collect promising news-outlet URLs from the search results. Apply the same ignore rules (drop Wikipedia, BBC profiles, social platforms, etc.) and the local-only filter above.
3. For each surviving candidate, follow the **First-time newspaper protocol** below.

Stop the WebSearch fallback once the country reaches 3 working sources or the search queries are exhausted. For single-source-only countries with no working candidate and no valid regional aggregator, write what you have and stop — don't fabricate.

**2d. First-time newspaper protocol (mandatory for every candidate from 2a OR 2c).**

For each candidate URL, before writing any YAML config:

1. Check whether the candidate has already been classified — look for an existing `<source>.yaml` or `_0_<source>.yaml` under `src/text/configs/<region>/<subregion>/<country>/`. If yes, skip — don't re-assess.
2. Otherwise, run `/assess-newspaper-source` against the candidate's base URL.
3. Act on the assessment tier:
   - **Tier 0** (verified JSON API): write the YAML using the WP API template (`references/yaml_templates.md`), then proceed to step 3 (categories) → step 5 (probe) → step 6 (rebuild).
   - **Tier 1** (clean HTML pagination, verified selectors): write the YAML using the pagination template, then proceed to step 5 → step 6.
   - **Tier 2** (scrapeable but needs custom code): write a `_0_<name>.yaml` stub per the `assess-newspaper-source` convention and skip — defer to a future onboarding pass.
   - **Tier 3** (unusable: SPA without API, Cloudflare-blocked, paywalled, dead): skip outright.

Only Tier 0 and Tier 1 candidates produce a working YAML. Do not fabricate configs for unverified candidates.

For diagnostic purposes only (when an assessment comes back surprising), the WordPress REST API can be probed directly:

```bash
curl -sL --max-time 6 -A "Mozilla/5.0" \
  "<base_url>/wp-json/wp/v2/posts?per_page=1&_fields=id,date,link,title"
```

Returns `[{"id":...}]` → Tier 0; `<!DOCTYPE html>` → try `?rest_route=/wp/v2/posts` fallback (Lesotho-Times pattern, see `references/known_quirks.md`); `Just a moment...` → Cloudflare; empty/4xx → unusable. `/assess-newspaper-source` runs these checks internally — you don't need to run them yourself unless debugging.

If after running step 2d on the entire candidate list you still have <2 Tier 0/1 sources for the country, the remaining escalation is:
- Add a **regional-aggregator fallback** config (next sub-section). This counts as a useful 3rd source.

**Regional aggregator: rules of use** (important — read carefully):

The fallback is only valid if the aggregator (a) is region-appropriate for the country being onboarded, and (b) exposes a stable per-country page or listing. Match the aggregator to the region; do **not** reuse one outside its geography.

Validated so far:
- **SSA (Sub-Saharan Africa)**: AllAfrica.com — per-country pages like `allafrica.com/<country>/`. Used for Ghana, Nigeria, Kenya, etc.

Not yet validated (do not assume an aggregator exists — verify before writing a config):
- **EAP, ECA, LAC, MENAAP, South Asia, Pacific**: no regional aggregator has been onboarded in this codebase. If the user is onboarding one of these regions, either (a) identify a real region-appropriate aggregator with a localized per-country section and assess it via `assess-newspaper-source` first, or (b) skip the fallback and accept fewer than 3 sources for countries with sparse local coverage.

**Hard rule**: never use AllAfrica for non-African countries. AllAfrica's coverage is geographically scoped to Africa; using it as a generic fallback would inject off-country content into the EPU index.

For single-source-only countries with no working candidate and no valid regional aggregator, write what you have and stop — don't fabricate.

### 3. Pick categories per source (the category filter rule)

**Rule** (project convention): scrape from a NATIONAL NEWS category first. If no "national" category exists, use ECONOMY + POLITICS (both, when available). If neither exists, fall back to LATEST/News.

Why: this reduces noise from sports/lifestyle/entertainment/international so the EPU index reflects national policy uncertainty rather than unrelated content.

Look up category IDs:

```bash
curl -sL --max-time 8 -A "Mozilla/5.0" \
  "<base_url>/wp-json/wp/v2/categories?per_page=100&_fields=id,name,slug,count"
```

Pick 2-5 IDs that match the rule, biased toward higher-count categories. Encode them as `&categories=ID1,ID2,ID3` in the API URL template. Skip categories that are clearly off-topic (`sport`, `lifestyle`, `entertainment`, `motoring`, `epaper`, `international`).

### 4. Write the YAML config

See `references/yaml_templates.md` for ready-to-paste templates:
- `wp_api_template.yaml` — Tier 0 WP REST API (the most common case)
- `pagination_template.yaml` — Tier 1 HTML pagination
- `regional_aggregator_template.yaml` — per-country regional-aggregator fallback (AllAfrica is the only validated example so far, SSA-only)

Place files at `src/text/configs/<region>/<subregion>/<country>/<source>.yaml`. Source key is the YAML basename — keep it short and underscored (e.g. `mail_and_guardian`, `the_villager`, `news_diggers`).

### 5. Probe each new source

**Mandatory test-before-rebuild**: every newly-written YAML (whether sourced from the static aggregator reference or the WebSearch fallback) is first probed with `--max-pages` and `--max-articles` flags. Only after the probe looks healthy does step 6 fire `--rebuild` for the full backfill.

Probe in batches of up to 8 in parallel:

```bash
python run.py text collect --source <key> --max-pages 1 --max-articles 50 -y
```

Why `--max-articles 50` and not larger: a 50-article sample gives a real success-rate signal (3/50 vs 50/50 are very different diagnostic states; 3/3 vs 3/3 is statistical noise) while keeping each probe under ~1 minute. WP API listing strategy doesn't strictly honor `--max-articles` — `--max-pages 1 × per_page=100` may land at ~100 thumbnails — but the per-article scrape attempts and the success counters scale with `--max-articles` and are what you check.

**Read the per-source counters from stdout, not just the exit code.** Each `--- <source> ---` block ends with lines like:

```
Thumbnails Discovered:           100
Articles Scraped:                 47
Failed (empty body):               2
Failed (empty date):               1
```

A green probe meets ALL of:
- `Thumbnails Discovered` > 0 (discovery works)
- `Articles Scraped` ≥ 0.7 × attempted (selectors and date both fire on the majority)
- `Failed (empty body)` and `Failed (empty date)` are each < 0.3 × attempted

A probe with `Articles Scraped: 0` despite `Thumbnails Discovered > 0` is a **broken-selector bug**, not "site is quiet today" — fix selectors before rebuilding. The most common cause for `type: api` configs is a placeholder `body: "filler"` left over from an old template; the pipeline silently falls back to per-URL HTML scraping when API content is empty, and "filler" can't possibly match. See `references/yaml_templates.md` for the required article-block selectors.

After the counters check out, also inspect `data/text/<region>/<subregion>/<country>/<source>/news.csv`:
- Has rows beyond the header
- `date` column parses as datetime (`pd.read_csv(...); pd.to_datetime(..., errors='coerce')`)
- `body` column has substantive text (not just nav/footer fragments)
- `title` column doesn't include obvious garbage (e.g. multiple titles concatenated → selector too broad)

A probe that returns **0 thumbnails**, **0 articles scraped despite >0 thumbnails**, or **0/N articles failed (HTTP error)** is a config bug — see `references/known_quirks.md` for the most common culprits before retrying.

### 6. Fire `--rebuild` for working sources

For each probe whose CSV looks good, dispatch a full rebuild in the background:

```bash
python run.py text collect --source <key> --rebuild -y
```

**Concurrency limits** (Pacific Observatory project policy):
- max **4 parallel `--rebuild` scrapes**
- max **8 parallel test probes**

When you hit the 4-rebuild ceiling, queue further rebuilds — wait for one to complete (you'll get a notification) before firing the next. The `--rebuild` flag is sanctioned by the project even though it briefly truncates `news.csv` mid-process; never use `rm` or any other destructive operation on `data/`.

While rebuilds run, advance to the next country's probes — you can productively overlap probe-test-budget (8) with the 4 rebuild slots.

### 7. Final tally

After all rebuilds complete, count rows per `news.csv` and report a per-country / per-source summary so the user can verify coverage.

```bash
for csv in data/text/<region>/*/*/news.csv; do
  rel=$(echo $csv | sed 's|data/text/||;s|/news.csv||')
  count=$(($(wc -l < $csv) - 1))
  printf '  %-50s %8d\n' "$rel" "$count"
done | sort
```

## Hard constraints (project policy)

- **Never delete or modify files under `data/` or `outputs/`** — the user handles destructive actions manually. `--rebuild` is allowed; `rm` is not.
- **Never commit files under `data/`, `outputs/`, or `openspec/`**.
- **Process countries sequentially** (one country's discovery + writing + probing finishes before the next country's begins) — but `--rebuild` scrapes from earlier countries can keep running in the background while you start the next country's probes.

## Quirks to bake in (from prior runs)

These are gotchas the skill should pre-empt rather than rediscover. Full detail in `references/known_quirks.md`.

- **Premium Times Nigeria** rejects `categories=...&_fields=...title...` with HTML 404. Drop `_fields` from the URL template; pipeline still parses the full JSON.
- **Lesotho Times** uses `?rest_route=/wp/v2/posts` (the legacy form), not `/wp-json/wp/v2/posts`.
- **WordPress `per_page` cap is 100** for most sites. Use `per_page=100` and let pagination handle the rest.
- **Regional aggregators rate-limit aggressively.** When using a regional-aggregator fallback (AllAfrica is the only validated example so far, SSA-only), a probe right after a heavy run may return 0 thumbnails. Write the config anyway — it'll work later.
- **Cloudflare-protected sites** to skip on first pass: most `*.guardian.*`, large national broadcasters, several .co.za papers (Maroela, IOL, BusinessLive, news24).
- **Arc Publishing CMS** (Times Live, Sunday Times, Business Live) has no WP API and uses obfuscated bundle paths — Tier 2/3, defer.
- **Eswatini Times** has a single wrapping container `div.col-md-6.HNews` around the whole news list (NOT per-article). Per-article cards are mixed `div.col-md-4` / `div.col-md-3`. Their relative `readmore.php` URLs need section-prefix rewriting; see `references/known_quirks.md`.
- **WP `categories=` filter URL-encoding**: when chaining multiple categories, e.g. `categories=3,60,24`, some CDNs treat the comma-list combined with `_fields` as bot-like. If a probe returns 0 thumbnails despite a manual curl returning JSON, drop `_fields` first.

## Suggested execution shape

For 8-16 countries, expect ~30-90 minutes wall time depending on archive depth. Coverage emerges in this rough order:

1. Resolve countries from `regions.yaml` (~30s)
2. Per country: read candidate outlets from `references/known_aggregators/<region>.md`, apply local-only filter, run `/assess-newspaper-source` per first-time candidate, write YAMLs for Tier 0/1 results, look up categories (~3-5 min/country). Fall back to WebSearch if the static reference is empty/exhausted.
3. Probe-test all configs in parallel batches of 8 (~2 min per batch)
4. Fire rebuilds in 4-at-a-time waves (each can take 1-30 min depending on archive size)
5. Final tally + summary

Keep the user informed at boundaries: per-country probe results, per-rebuild completion notifications, final tally. Don't narrate every curl.

## Concurrency note for parallel firing

When firing many sources at once (rebuilds OR probes), use shell `&` backgrounding within a single bash call:

```bash
for src in src1 src2 src3 src4; do
  python run.py text collect --source $src --rebuild -y > /tmp/rebuild_$src.log 2>&1 &
done
echo "fired $#"
```

This is more efficient than spawning each in its own `run_in_background:true` Bash call (which has higher per-call overhead) and respects the concurrency limits when you batch-size correctly.

## Reference files

Read these as needed (don't load them upfront):
- `references/known_aggregators/<region>.md` — pre-extracted per-country newspaper outlet lists from w3newspapers, onlinenewspapers, allyoucanread, abyznewslinks (used by step 2a)
- `references/known_aggregators/README.md` — fetching tools, ignore rules, refresh instructions for the aggregator data above
- `references/yaml_templates.md` — copy-paste YAML for the three config types
- `references/known_quirks.md` — per-site CDN/auth/selector workarounds discovered in prior runs
- `references/category_lookup.md` — common WP category slugs to map to IDs

## Output format expected by the user

After processing, return a **terse** per-country summary:

```
## <region>/<subregion>

### <country> (3/3 working | 2/3 working — see notes)
- <source_key>: <article_count> rows | <date_min> → <date_max>
- ...

## Issues / deferred
- <country>/<source>: <reason>
- ...

## Total: <N> articles across <M> sources
```

Background `--rebuild` processes that haven't finished by the time you return are fine to mention as "still running, will complete autonomously" — the user knows this is normal.
