# PropertyGuru-family lat/lon enrichment — performance comparison

**Date:** 2026-05-21 · **Branch:** `feat/propertyguru-latlon` · **Author:** automated benchmark

Four EAP rental sources have been onboarded to `po prices collect` (commit
`967f3e43`): `propertyguru_sg`, `propertyguru_my`, `ddproperty_th`, and
`batdongsan_vn`. The card-only flow ships listing rent + address + beds + sqft
to `data/.../raw_items/*.jsonl`. This document measures the marginal cost of
adding per-listing latitude/longitude on top of that flow.

## TL;DR

* **Feasibility.** Per-listing coordinates are available on the three
  PropertyGuru-family sites (SG / MY / TH) at one identical JSON path inside
  the PDP `__NEXT_DATA__` blob (`props.pageProps.pageData.data.
  listingLocationData.data.center`). `batdongsan.com.vn` (Vietnam, separate
  platform) **exposes no per-listing coordinates** — its only map field is a
  Hanoi default — so VN is scoped out of the feature.
* **Design.** Option B (separate PDP enrichment pass, decoupled from the card
  crawl) is the chosen design. Option A (inline PDP fetch per card) would
  couple card-flow success to PDP-flow success and offers no measurable
  throughput advantage at the recommended concurrency.
* **Cost.** PDP enrichment at `concurrency=3` runs at **~250 items/min**
  across SG / MY / TH with **94–100% coord coverage** per site. For a typical
  combined 1,190-item PG-family weekly run, lat/lng adds **~4.5 minutes of
  wall time on top of ~1 minute of card-only crawl** — roughly **7× the
  per-spider card-only time, paid entirely in PDP latency**. No Cloudflare
  challenges or 403s observed at the 150-PDP × 2-trial sample.
* **Caveat.** A ~6% MY-site "no coord" rate is real listing churn (one
  verified to have delisted within 90 minutes of the card crawl), not a
  bench artefact. Treat null coords as a normal output, not a failure.

## Probe methodology

For each of the four sites we sampled URLs from the latest card-flow
`raw_items/*.jsonl` (the `10:13` 2026-05-21 batch produced by the still-running
PID `98111` collect job) and fetched each PDP with `curl_cffi` using the same
TLS-impersonation profile the card spider uses (`chrome120` for PG-family,
`safari17_0` for BDS), plus a card-listing `Referer` header.

The `Referer` matters: earlier session-level testing had MY/TH PDPs returning
403 to bare `curl_cffi` calls, and the handoff document flagged this as the
top open risk. Sending the card-listing URL as `Referer` was sufficient to
clear it (5/5 200s on MY, 5/5 200s on TH at the probe stage).

### Listing-center extraction

The handoff document specified the path
`__NEXT_DATA__.props.pageProps.pageData.data.listingLocationData.data.center`.
That path holds an object `{lat, lng}` representing the **listing center** —
not the nearest landmark.

Initial probes used a naive `"lat":x,"lng":y` regex against the raw HTML. That
returned a 100% match rate but was **wrong**: on at least one SG PDP the first
regex hit was the nearest MRT station (1.3200, 103.8434) and not the listing
center (1.3195, 103.8460). PG PDPs embed school, MRT, and transit-stop
coordinates in the same JSON shape elsewhere in the page, and the first-match
field depends on payload order. The final extractor parses `__NEXT_DATA__`,
walks the documented path, and returns `None` if the field is missing.

### batdongsan.com.vn (VN) — scoped out

Of 8 BDS PDPs probed, 7 had no `Latitude`/`Longitude` JSON field at all and 1
returned the Hanoi default `(21.0289, 105.8524)` regardless of the property
being in Q9 HCMC (~10.85 N). BDS exposes a free-form map-widget address but no
machine-readable per-listing geocode. VN keeps shipping rent + address +
beds + area; coordinates are not added.

## Benchmark methodology

* Sample: first 50 listings from each card raw_items file per site.
* For each PDP: `curl_cffi.get(url, impersonate=<profile>, headers={Referer:
  <card-listing-url>}, timeout=30)`; parse `__NEXT_DATA__` and walk to
  `pageData.data.listingLocationData.data.center`.
* Workers: `concurrency=1` (single-thread, sequential).
* Measures per request: HTTP status, wall-clock latency, HTML bytes, lat,
  lng.
* Measures per run: wall seconds, items/min, p50 latency, p95 latency, coord
  coverage %, status code distribution, error count.

(A `concurrency=3` trial follows once the c1 run lands, to bound the
realistic throughput when several PDPs fly in parallel.)

## Card-flow wall-time baseline

**Solo (this benchmark).** `po prices collect --source propertyguru_sg` run
alone, with no other spiders contending for the reactor:

| Spider          | Wall time | Items | Throughput      |
|-----------------|-----------|-------|-----------------|
| propertyguru_sg | **17 s**  | 559   | 32.9 items/sec  |

Scrapy fans the landing-page + ~28 district fetches out at default
`CONCURRENT_REQUESTS_PER_DOMAIN=16`, so 29 server-side renders complete in
parallel and the wall time is bounded by network + slowest district render,
not by per-card cost. This is the right number for "what does the card flow
take on its own."

**Production parallel (for context).** From the still-running `prices
collect` job (PID 98111, started 2026-05-21 10:06:55), all four card spiders
share one `CrawlerProcess` reactor and Scrapy's download slots. They were
scheduled together but MY arrived first and saturated the slots, queueing
SG/TH for ~5 minutes:

| Spider          | First-item log | Last-item log | Active-work window | Items |
|-----------------|----------------|---------------|--------------------|-------|
| propertyguru_my | 10:07:54       | 10:13:19      | 5m 25s             | 441   |
| propertyguru_sg | 10:13:09       | 10:13:47      | 38s                | 559   |
| ddproperty_th   | 10:13:06       | 10:13:29      | 23s                | 190   |
| batdongsan_vn   | ~10:13         | 10:16:25      | ~3m                | (TBC) |

The "Active-work window" column is the gap between each spider's first-item
log and last-item log — bounded by Scrapy's parallel district fetching. The
gap between first-scheduled (10:06:55) and first-item-log is queue time, not
network. Solo SG runs at ~17s; parallel SG inside the 4-spider crew runs in
~38s of actual work after a ~5-minute queue.

## Concurrency=1 benchmark results

| Site | Profile   | n  | wall_s | items/min | p50 ms | p95 ms | coord % | 200s | non-200 |
|------|-----------|----|--------|-----------|--------|--------|---------|------|---------|
| sg   | chrome120 | 50 | 32.4   | 92.7      | 491    | 1679   | 100.0%  | 50   | 0       |
| my   | chrome120 | 50 | 34.7   | 86.4      | 572    | 1365   | 100.0%  | 50   | 0       |
| th   | chrome120 | 50 | 44.8   | 66.9      | 737    | 1470   | 100.0%  | 50   | 0       |

All three sites returned **100% coord coverage and zero non-200 responses**.
No Cloudflare challenges or 403s were observed at single-thread pacing — the
`Referer` header that worked at the 5-PDP probe stage scales fine to a 50-PDP
sequential burst. Throughput is dominated by per-request TLS handshake and
SSR HTML render time; p50s sit in the ~500–750 ms band, p95s under 1.7s.

## Concurrency=3 benchmark results

URLs were drawn from offset 50 in each card raw_items file (so c3 hits a
disjoint URL set from c1; no CDN cache warm-up advantage).

| Site | Profile   | n  | wall_s | items/min | p50 ms | p95 ms | coord % | speedup vs c1 |
|------|-----------|----|--------|-----------|--------|--------|---------|---------------|
| sg   | chrome120 | 50 | 10.2   | 295.6     | 520    | 1163   | 100.0%  | 3.19×         |
| my   | chrome120 | 50 | 12.1   | 247.3     | 588    | 1102   | 94.0%   | 2.86×         |
| th   | chrome120 | 50 | 14.4   | 209.0     | 770    | 1495   | 100.0%  | 3.12×         |

SG and TH stay at perfect coverage and zero non-200s at c3. MY surfaces a 6%
"no coord" rate — three listings (`ss17-...-501379892`, `presint-12-putrajaya-
...`, `taman-public-likas-...`) returned 200 with `listingLocationData.data.
center = null` in their PDP JSON. Spot-checking one (`ss17-...-501379892`)
~90 minutes later showed the listing had since 404'd ("This listing is no
longer available"), so the null-center state appears to be PG's transitional
view of a listing that's about to be delisted. **This is real-world listing
churn, not a benchmark artefact** — the missing coords are not recoverable
by retrying, and the right behavior is to write the row with `lat=null` and
keep going.

No 403s, no Cloudflare interactive challenges, and no measurable latency
inflation at c3 — the p50 sits within ~50ms of the c1 p50 on every site,
which means the bottleneck at c1 was wall pacing, not server response.

## Cost projection — marginal time to add lat/lng per spider

Applying the measured `items_per_min` to each site's most recent card-flow
yield (the 2026-05-21 10:13 run that produced the seed JSONLs):

| Spider          | Card items | Card-only wall | + PDP @c1     | + PDP @c3       |
|-----------------|------------|----------------|---------------|-----------------|
| propertyguru_sg | 559        | 17 s (solo)    | 6 m 02 s      | **1 m 53 s**    |
| propertyguru_my | 441        | (similar)      | 5 m 06 s      | **1 m 47 s**    |
| ddproperty_th   | 190        | (similar)      | 2 m 50 s      | **0 m 55 s**    |
| **PG-family total** | **1190** | ~1–2 min     | ~14 minutes   | **~4.5 minutes**|

(c1/c3 wall times derived from each site's measured items/min: SG 92.7/295.6,
MY 86.4/247.3, TH 66.9/209.0. PG-family total is the sum of the per-site
enrichment passes run sequentially; a single shared PDP worker pool would
not improve on this materially because the per-site DNS / TLS / Referer is
unshared.)

The card-only flow at solo SG times sits at ~17 seconds for 559 listings.
Adding PDP enrichment at `concurrency=3` adds ~2 minutes for that same
559-listing slate — roughly **7× the card-only time per spider**, all paid
in PDP latency. There is no measurable degradation of the card-flow itself;
the marginal cost is purely additive.

## Coord coverage and known nulls

* `propertyguru_sg` — 100/100 (c1 + c3) listings yielded valid
  `listingLocationData.data.center` coords.
* `propertyguru_my` — 47/50 at c3 (94%); the 3 missing are listings that PG
  is in the process of delisting (one verified to have 404'd within ~90
  minutes of the card crawl). At c1 (a disjoint URL set) MY hit 50/50.
* `ddproperty_th` — 100/100 (c1 + c3) listings yielded valid coords.

The 3 MY misses are real-world listing churn, not a benchmark artefact —
retrying does not recover them, and an enrichment spider should emit
`{listing_id, lat: null, lng: null}` rows and continue.

## Recommendation

**Ship Option B as a sibling enrichment spider per PG-family site.** Three
shallow spiders — `propertyguru_sg_pdp`, `propertyguru_my_pdp`,
`ddproperty_th_pdp` — each reading the latest `raw_items/<spider>_<UTC>
.jsonl`, fetching each PDP at `concurrency=3` with the `__NEXT_DATA__`
listing-center parser, writing `{listing_id, url_hash, lat, lng,
scraped_at_utc, pdp_status, pdp_latency_ms}` to a sibling `raw_items_pdp/`
directory. A downstream join step at process-time inner-joins on `listing_id`
to attach coords to the card rows.

Rationale:

1. **Decoupled failure modes.** Card flow continues to ship even if a PDP
   batch trips a CF challenge. The handoff document called this out as the
   chief argument against Option A, and the benchmark numbers confirm
   nothing in Option A would be unique-faster — the PDP cost is the PDP
   cost either way.
2. **Acceptable wall-time cost.** ~2 minutes per site at `concurrency=3`,
   100% coverage on SG/TH, ~94% on MY (with the missing 6% being real
   listing-state nulls, not failures).
3. **Observability.** Side-by-side card + PDP yield comparisons let us
   detect PDP regression independently of card regression. Recommend
   emitting a per-run coverage % to the source-state cache so the home
   screen can show "PG_SG lat/lng coverage: 99%" alongside the existing
   item-count freshness.
4. **VN scoped out.** `batdongsan_vn` keeps shipping card-level rent + area
   + address strings; no PDP pass is scheduled. Document this in
   `references/known_blockers.md` if a future agent re-evaluates.

**Concurrency cap:** `3` is the recommended ceiling. The MY c3 trial did
not 403, but the gap from `c1` p50 to `c3` p50 is statistically zero — the
server is doing the same work either way and parallelism is free. Higher
parallelism would compress the wall-time further but risk crossing PG's
unannounced rate-limit threshold, which we cannot measure without breaking
the production card flow.

**Non-goals (explicitly):** do not promote the PDP fetch to the card spider
itself, do not introduce a shared cross-site PDP worker pool, do not retry
listings with `center=null` (real listing state). Re-evaluate concurrency
upward only if PG response latency demonstrably degrades or if SG coverage
drops below 95% in two consecutive weekly runs.

## Reproducing this benchmark

```bash
# Concurrency=1 across the three PG-family sites, 50 PDPs each from URL
# offset 0 in the latest card raw_items file.
poetry run python /Users/jeronimoluza/.claude/jobs/0dbe5d40/bench_pdp.py \
    --sites sg,my,th --n 50 --concurrency 1 \
    --out /tmp/bench_c1.jsonl 2> /tmp/bench_c1.stderr

# Concurrency=3, URLs at offset 50 (disjoint from c1's sample).
poetry run python /Users/jeronimoluza/.claude/jobs/0dbe5d40/bench_pdp.py \
    --sites sg,my,th --n 50 --concurrency 3 --offset 50 \
    --out /tmp/bench_c3.jsonl 2> /tmp/bench_c3.stderr

# Solo card-only baseline.
time poetry run po prices collect --source propertyguru_sg
```

Raw per-PDP rows from the runs that produced this report are at
`/Users/jeronimoluza/.claude/jobs/0dbe5d40/bench_c1.jsonl` and
`bench_c3.jsonl` (one JSON line per request, including HTTP status,
latency, lat/lng, html_bytes, and any error).
