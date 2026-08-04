# 2026-07-31 — Wayback bulk-CDX discovery + weekly collapse; fetch-bottleneck research

## Goal

We added a lot of new product URLs to the prices pipeline and want to backfill
their history. Two historical backfillers exist and feed the **same** enrich
stage (`enrich/stages/concatenate.py` reads `raw_items/`, `wayback_items/`, and
`common_crawl_data/items/` equally). **Common Crawl is fast and left untouched.**
**Wayback was "very very slow"** — this session diagnosed why, fixed it, and
scoped what can (and cannot) be done about the fetch side.

## Lay of the land — why Wayback was slow

| | Common Crawl (`cc_warc_fetcher.py`) | Wayback (`backfill.py` + `_shared/wayback.py`) |
|---|---|---|
| **Discovery** | 1 bulk index query per (spider, index), paged → ~40 calls maps a whole source, with byte offsets | **1 CDX call *per URL*** — the anti-pattern |
| **Fetch** | HTTP Range GET → `data.commoncrawl.org` (S3/CloudFront, unmetered), 8 workers | `web.archive.org/…id_/` playback endpoint — rate-limited, **L4-blackholes** under concurrency, 4 workers |

Discovery cost quantified on the new URL universe: **cosmed 174,738 unique URLs,
rakuten 334,990, pickaroo 213,183, carrefour_tw 188,196, aeon_online 91,996** —
~1M serial CDX calls for just 5 sources *before* fetching a snapshot. CC does the
equivalent in ~40 calls.

## Shipped — bulk-CDX discovery + weekly collapse

Mirrors CC's bulk discovery. **CC untouched.**

**`src/prices/_shared/wayback.py`** (+~180 lines):
- `bulk_discover(session, universe, cutoff, granularity="week")` → `{url_hash: [ts]}`.
  One paged CDX query **per host** instead of one per URL. Intersects CDX
  `original` URLs against the universe (so only products we collected get
  backfilled) and collapses to `granularity`.
- `collapse_timestamps(ts, granularity)` — client-side dedup to one snapshot per
  `day`/`week`/`month`/`year` bucket, keeps earliest. **Weekly has no CDX
  digit-prefix, so it must be client-side** (also why server-side collapse can't
  be used — see below).
- `_derive_scopes(urls)` — group by host → `host + longest-common-path-prefix`
  (trimmed to last `/`), `matchType=prefix`. Single-tenant tightens
  (`shop.cosmed.com.tw/SalePage/Index/`); multi-tenant falls back to host
  (`item.rakuten.co.jp/`). No per-spider config needed.
- `_norm_url` — scheme/case/trailing-slash-insensitive intersection key.
- `iter_bulk_captures` — pages the CDX `page=` API. **No server-side collapse**:
  collapsing adjacent rows on a multi-URL query drops the first capture of a URL
  when it shares a bucket with the previous URL's last capture.

**`src/prices/backfill.py`**: `backfill_one_url` gained `timestamps`/`granularity`
(skip per-URL discovery when precomputed); `run_source_backfill` gained
`discovery` (`bulk`|`per-url`) + `granularity`, runs ONE `bulk_discover` pass then
routes precomputed timestamps per `url_hash`. CLI split out to
**`src/prices/backfill_cli.py`** (backfill.py had passed the 500-line hard limit;
now 444). `cli.py` import updated. **New CLI defaults: `--collapse week` (was
`day`), `--discovery bulk`.** `per-url` still available.

## Two bugs the live tests caught (both fixed)

**Bug 1 — pagination silently disabled (critical, would hit every big source).**
`_cdx_num_pages` sent `showNumPages=true` **with `output=json`** → CDX returns
`[["original","timestamp"],[null,null]]`, not a bare int → `int()` fails →
returns `None` → pagination off → single unpaged call hits CDX's default row cap.
On sources with many captures under the prefix, the cap fills with earliest-urlkey
siblings (rbpatel: all `/product-category/` listing pages, which sort *before*
`/product/` and aren't in our universe) → **intersection 0** even though per-URL
discovery finds 8/4/8 snapshots. Small sources (molisi/food_pro/mh_online) only
worked because they fit under the cap.
**Fix:** rewrote `iter_bulk_captures` to **page until an empty page** (dropped the
flaky `showNumPages`/`_cdx_num_pages` dependency entirely; `_MAX_BULK_PAGES=500`
backstop). After the fix, **rbpatel 0 → 843/896 URLs**, per-URL-equivalent exactly.

**Note (not a bug):** prefix scope `x/product/` canonicalizes to a urlkey without
the trailing slash, so it prefix-matches `/product-category/` too. Paging now
walks past those and the intersection filters them out — correct, just extra
index bandwidth.

## Fetch bottleneck — research (the hard part)

The fetch step is IA's playback endpoint (`web.archive.org/web/{ts}id_/{url}`),
which rate-limits and **L4-blackholes** aggressive clients (`[[wayback_ia_blackhole_risk]]`,
`[[eap_wayback_v3_sigterm_20260521]]`). food_pro at `workers=4` wrote **155 valid
rows then IA refused every connection** (`[Errno 61] Connection refused`).

**Key negative finding (tested, saves re-research):** the structural fix — fetch
raw WARC records by byte-offset like CC does — is **blocked on the public CDX**.
Probed `fl=timestamp,original,statuscode,filename,offset,length`: **`filename` and
`offset` come back `null`** (only `length` populated). IA withholds WARC locators
on the public CDX to prevent direct petabox fetching. **So Wayback fetch cannot be
made CC-fast on the public API.** Bulk discovery fixed *discovery* (~1000× fewer
calls); the *fetch* remains IA-bound.

Fetch approaches (ranked — none make it CC-fast; several make it reliable/faster):

- **A. Circuit-breaker + gentle pacing** *(explore next)* — blackhole is
  burst-triggered & per-IP. 1–2 workers, steady ~1–2 req/s, honor `429/503
  Retry-After`, reuse ONE keep-alive connection (today `_process` wastefully calls
  `make_session()` per URL), and on repeated connection-refused **pause the whole
  run 5–15 min then resume from the ledger** instead of burning through failures
  and dying. Would have kept food_pro alive.
- **B. Cut fetch volume** — monthly collapse instead of weekly (2–4× fewer;
  prices don't move weekly); skip timestamps CC already covers.
- **C. CC-primary, Wayback gap-fill** *(explore next)* — widen `SPIDER_CC_CONFIG`
  + pull more CC indexes; use Wayback only for URLs/dates CC misses.
- **D. Ask IA for research access** — nonprofit, supportive of academic/nonprofit
  work (World Bank price-index use). Could whitelist an IP / grant WARC-locator or
  bulk access → re-opens the CC-speed path. An email.
- **E. DISCOURAGED** — multi-IP evasion. Per-IP block means it'd multiply
  throughput, but deliberately evading a nonprofit's limits is poor citizenship.

**Recommendation:** B+C now (cheap, use what works), implement A so runs survive,
send D in parallel.

## Verification

- Offline unit logic: `collapse_timestamps`, `_norm_url`, `_derive_scopes`,
  `iter_bulk_captures` (page-until-empty), `bulk_discover` intersection.
- Live: molisi 1 CDX query replaced 346 per-URL calls; rbpatel 843/896 post-fix;
  bulk == per-URL timestamps exactly on samples; food_pro wrote 155 real rows
  end-to-end (bulk→fetch→parse→write) before the blackhole.
- `ruff` clean; **10 wayback + 4 backfill-runner unit tests pass** (5 new).
- Pre-existing unrelated failure: `test_backfill_loader::
  test_load_url_universe_skips_rows_missing_url_or_hash` (`load_url_universe`
  synthesizes `md5(url)` for aggregator rows; untouched here).

## Test method (reuse this)

Isolate a per-source run **outside `data/`**: `$CLAUDE_JOB_DIR/tmp/<src>_full`
with `raw_items` symlinked to the real source and a fresh ledger — existing data
is never touched. A **discovery-only probe** (`bulk_discover`, no fetch) cheaply
vets whether a site archives well before committing to a fetch:
molisi=DEAD (per user), rbpatel=843/896, mh_online=3266/7897, food_pro=178/181.

## State & backlog

- **Uncommitted** on branch `template-repo` (user's checkout has many unrelated
  changes; not committed pending review). Files: `src/prices/_shared/wayback.py`,
  `src/prices/backfill.py`, `src/prices/backfill_cli.py` (new), `src/cli.py`,
  `tests/unit/prices/test_wayback_transport.py`.
- **Next: explore A (circuit-breaker/pacing) and C (CC-primary gap-fill).**
- Not yet run at scale — measure wall-time on a big source (e.g. cosmed 174k) once
  A makes runs survivable.

Related memory: `[[bug-wayback-bulk-cdx-two-findings-from-live-testing-on]]`,
`[[bug-wayback-fetch-bottleneck-research-menu-key]]`,
`[[bug-prices-historical-backfill-wayback-vs-common-crawl-efficiency]]`.
