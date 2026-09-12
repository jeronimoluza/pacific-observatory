# AWS Common Crawl Sweep — Cookbook

Everything needed to run a Common Crawl historical-price sweep on AWS, written
2026-09-12. Every number here was measured, not estimated; where something is
unverified it says so.

The goal of a CC sweep is **historical price series**. Live scraping gives you
today; CC gives you 2013 onward for the same hosts. It is the only route to
pre-2020 price levels for most of the corpus.

---

## 0. The one-paragraph version

Resolve and fetch are **separate jobs with opposite requirements**. Resolve
turns a source's URL prefix into WARC byte-ranges and needs the 13 GB
`cluster.idx` cache. Fetch turns byte-ranges into rows and needs nothing but the
manifest. Read WARCs **from `s3://commoncrawl` in us-east-1, never from the
public CDN** — S3 is `Payer=BucketOwner` (Common Crawl pays), has no ban
behaviour, and sustained 228 rec/s at concurrency 64 with zero failures. The
public CDN bans your whole IP after ~20k requests. Parse is CPU-bound pure
Python, so **instance count is the only throughput lever**. A full 102-crawl
fleet pass is ~9.4 h on 8 instances for **~$7**.

---

## 1. Hard-won facts that change the plan

| Fact | Consequence |
|---|---|
| `s3://commoncrawl` is `Payer=BucketOwner` (verified with `GetBucketRequestPayment`) | Reading the whole 2.6 TB archive costs **nothing** in request or transfer charges. An earlier ~$23 estimate assumed Requester Pays and was wrong. Your only costs are EC2 compute, EBS, and egress of parsed output. |
| The public CDN (`data.commoncrawl.org`) bans by **concurrency**, not rate | Keep concurrent connections **≤ 12** there. 32 connections 403s immediately even at a *lower* per-connection rate. Recovery is ~5 min but retrying through it extends the ban. Prefer S3 and the problem disappears. |
| CC returns **403, not 429** | A fetcher that returns `""` on non-200 makes a throttled index look like an uncrawled site. In one early sweep 3 of 14 indexes reported zero records for all 185 sources — the harness said "no data" when it meant "I was blocked". **Any CC loop MUST count non-200s separately from empty results.** |
| Parse is pure Python and holds the GIL | CPU sat 95-99% for a 73-min run. Raising `CONC` buys nothing beyond the S3 fetch. One process per vCPU; scale by instance count. |
| Ban is per **address**, not per NAT | The Pi 403'd on IPv6 while the Mac got 206 from the same network. Two machines behind one public IP share the ban budget — run resolve and fetch as phases, not in parallel at full width. |

---

## 2. Cost and time arithmetic (measured 2026-08-28)

One `c7i-flex.large` ran the full `CC-MAIN-2017-30` manifest (801,366 captures)
as 2 shards:

- **91.2 rec/s per process.** Both shards finished within 1 second of each other
  (4392 s vs 4393 s), so `i % NSHARDS` line-sharding balances essentially
  perfectly.
- No `c7i-flex` throttling over 73 minutes at sustained 100% CPU. The 40%
  baseline did not bite at that duration — **do not assume it holds for much
  longer runs.**

Fleet: 49.2M captures ÷ (16 processes × 91.2 rec/s) ≈ **9.4 h on 8 instances**
(16-vCPU quota cap; quota `L-1216C47A` is adjustable). At $0.08479/hr that is
**~$7 all-in**. Output is ~60 bytes/row gzipped, so a whole parse lands near
1.7 GB — under the 100 GB free egress threshold.

Latency is flat at ~167 ms per GET regardless of concurrency, so the job is
latency-bound and concurrency is the only lever *for the fetch half*:

| concurrency | rec/s | MB/s | p95 ms | failures |
|---|---|---|---|---|
| 1 | 5.7 | 0.29 | 236 | 0 |
| 8 | 44.2 | 1.54 | 272 | 0 |
| 32 | 146.7 | 9.20 | 405 | 0 |
| 64 | 228.1 | 16.36 | 425 | **0** |

Zero 403s at 64 over S3. None of the CDN ban behaviour appeared.

---

## 3. The AWS floor (already deployed)

CloudFormation stack **`cc-guardrails`**, us-east-1, account `934494149338`,
CREATE_COMPLETE since 2026-08-27. Template lives in the repo under `infra/`.

- **Budget** `cc-fetch-monthly` — $50/month, alerts at 50/80/100% ACTUAL plus
  100% FORECASTED, to jero.luza@gmail.com.
- **Bucket** `pacific-observatory-cc-warc-934494149338` — Intelligent-Tiering at
  day 0, aborts incomplete multipart uploads after 7 days, all four
  public-access blocks on, AES256, `DeletionPolicy: Retain`.
- **Role** `cc-fetch-ec2-role` + instance profile **`cc-fetch-ec2-profile`** —
  reads `commoncrawl`, writes only our bucket, may terminate instances tagged
  `Project=cc-fetch`. **No long-lived access keys exist anywhere.**
- **Managed policy** `cc-cost-guardrails` — explicit Denies that outrank any
  grant: non-us-east-1 `RunInstances`/`CreateVolume`/`CreateDBInstance`;
  instance types outside a t4g/c7g/m7g allowlist capped at c7g.8xlarge;
  `CreateNatGateway`; `CreateVpcEndpoint`.

Guardrails were verified with `iam SimulatePrincipalPolicy`, not assumed:
c7g.large and t4g.micro in us-east-1 → allowed; p5.48xlarge → explicitDeny;
c7g.large in ap-northeast-1 → explicitDeny; CreateNatGateway → explicitDeny.

### Two standing account caveats

1. **Cost Explorer is not enabled and there is no API to enable it.** That
   blocks Cost Anomaly Detection. Enable once in the Billing console, wait ~24 h,
   then add `AWS::CE::AnomalyMonitor` + `AnomalySubscription` to the stack.
2. **The free plan auto-closes the account on 2027-02-27 and DELETES data.**
   Nothing durable may live in this S3 bucket. Treat it as scratch; pull results
   down.

---

## 4. Running it

### 4.1 Resolve (needs the index cache)

```
prices/cc_resolve.py          # library
prices.tools.cc_resolve_run   # driver
```

- Needs `cluster.idx`: **13 GB on disk for ~123 crawls**, ~0.3 GB RAM per crawl
  to parse. The Mac already holds this cache at
  `template-repo/data/prices/_cc_index` (15 GB, 123 crawls) — the expensive
  artifact. Don't re-download it.
- **Resolve is index-major on purpose.** Source-major re-parses all ~123 indexes
  per source: identical output for 623× the parse work and ~8 TB of redundant
  reads of the same 13 GB.
- `cc_index._CLUSTER_CACHE` is bounded to 2 entries (`_CLUSTER_MAX_RESIDENT`).
  It was unbounded and climbed to ~25 GB resident over 103 indexes, hard-rebooting
  the Pi around index 15. The bound costs nothing — hit rate was zero.
- The cdx layer **is readable from S3**, so resolve can run in-region next to
  fetch rather than over the throttled CDN. That is what unblocks the
  101 unresolved crawls.

Manifest layout: `_cc_manifests/by_index/<crawl>.jsonl` → consolidated to
`by_source/<spider>.jsonl`. **~425 bytes/record** (long WARC filenames dominate).
Ship only `by_source/` to the fetch machine.

### 4.2 Fetch (needs nothing)

```
prices/cc_fetch.py
prices common-crawl --manifest PATH
```

Needs only `filename` / `offset` / `length` per record. Runner is
`infra/fetch/run.sh`.

**Gotcha:** a missing manifest reports `NO_MANIFEST` rather than falling back to
local index resolution — on a cacheless machine that fallback would silently
start a 13 GB download.

### 4.3 Getting files onto an instance

The EC2 UserData limit is 16 KB, so don't inline manifests:

1. `get_presigned_url(operation="upload")`
2. `curl -T` from the Mac
3. a ~230-byte UserData that does `aws s3 cp s3://<our-bucket>/... /tmp/`

**UserData must contain no shell metacharacters** (`>`, `|`, `&`) or the aws-mcp
proxy refuses the `run-instances` call. `exec > >(tee /dev/console)` is rejected.
Let cloud-init do the logging.

Also: `run-instances` through the proxy needs `--count 1`; omitting it fails with
"Missing required parameter MinCount/MaxCount". And **GetConsoleOutput stayed
empty for the whole life of a 2-minute instance** — write results to S3, do not
plan on reading the console for short-lived instances.

### 4.4 Ops pattern that worked

Keyless instances ship logs to `s3://<bucket>/logs/<instance-id>/` every 60 s and
self-terminate via the role's tag-scoped `ec2:TerminateInstances`
(`Project=cc-fetch`). Nothing is left billing and the evidence outlives the box.

---

## 5. Four silent truncation traps

All four shipped as "completed" runs that quietly lost data. Fixed 2026-08-19
(`1ce47ade`), but know the shapes:

1. **`--max-per-index 400`** — the biggest. On `auchan_ro` it dropped **47,205 of
   62,571 records (75%)**. Correct for a *sampling* run (spreads a fixed budget
   across crawls so you get repeat observations of the same product), wrong for a
   full backfill. Now `0` = unlimited.
2. **`max_blocks=400` in `query_prefix`** — truncated **discovery**, not fetch:
   URLs past the 400th cdx block are never enumerated, so nothing downstream can
   tell they existed. Logged a warning no summary read.
3. **`--since 2016` ≈ 103 crawls; since 2013 ≈ 123.** Twenty crawls never
   queried. Default is now 2013.
4. **`resolve_cc_indexes` fell back to 8 recent crawls** when `collinfo.json`
   504s — which it does intermittently. A run hitting it collects months instead
   of years, reports `completed`, and shows nothing wrong. Now `strict=True`
   raises, and the driver **pins the resolved crawl list to a file** so the set is
   identical across machines and resumes.

### The asymmetry that matters most

The wall-clock cap is **not** destructive — a timed-out source resumes from what
it saved, because the skip set is built from written item files. But:

- `no_extract` pages write **nothing**, so they are re-fetched every pass. A
  source with a broken parser re-pays its fetch cost each run until fixed.
- A page that yielded 1 row **is** in the skip set, so a parser fix that would
  now yield 40 **never revisits it**.

**Failures self-heal; under-extraction does not.** Fix parsers before big sweeps.

---

## 6. Where the yield actually comes from

- **Parse coverage is inverted by volume.** 45.4% of spiders can parse archived
  markup, but those spiders are only 0.4% of RECORDS. The top 66 sources by
  volume are bespoke and untested.
- **Microdata is the workhorse on old crawls.** On CC-MAIN-2017-30: 315,051
  microdata vs 116,710 JSON-LD vs 30,075 meta, out of 801,366 captures giving
  462,738 rows (57.7% of captures yield). Without the microdata tier that crawl
  returns 146,785 rows — the tier is worth **3.15×** there. `flight` scored 0, as
  expected for 2017.
- **JSON-LD is 0% pre-2016 and ~46% by 2026.** Fixing the fall-through is worth
  ~5.18× usable rows.
- **JSON-LD misses are mostly malformed JSON** — repair recovers 27.2%
  (+167k rows) with **zero overlap** with the microdata recovery. They are
  additive, not competing.
- **Repeat rate is 15% pooled but 20-77% for grocers and pharmacies.** One crawl
  per year is why 2013-24 has no dense series for most hosts.

---

## 7. Known-open item: the bysource tier

`ccfetch.py:222` passed `rec.get("source")` but manifest rows carry `spider`.
Result: **zero firings across 20,194,316 r8a records.** Fixed on
`prices/fill-gap-sources` (and now `prices/precision-sweep`) at commit
`f5a3e109` — the line now reads `rec.get("spider") or rec.get("source")`.

**The recovery run is the highest value-per-dollar item outstanding**, and needs
no further code change:

```
INPUT=misses   over  misses-r8a/ and misses-r8b/
```

22,950,935 records (`archived_bysource.py` covers 35.7% of r8). Miss records DO
carry `source`, so they re-dispatch correctly now. All three input prefixes
(`misses-r8a/`, `misses-r8b/`, `misses-r9/`) are present in S3 and verified.

---

## 8. Prefix hygiene — read before shipping `archive_prefix`

`archive_prefix` is applied as a plain
`line.startswith(surt_prefix(archive_prefix))` at `cc_index.py:351`, **before**
`archive_path_re`. Consequences:

- `surt_prefix()` does `path.rstrip("/")`, so `/p/` also matches `/pampers`.
- `path_re` is `re.search` against `urlparse(url).path` only — **no query
  string** — so `^...$` anchors are load-bearing.
- `surt_prefix` lowercases, but the regex sees original case.
- Percent-encoding uses **UPPERCASE** hex.

**Live-derived prefixes are measured wrong.** Only 35 of 84 shipped prefixes
returned any records, versus 45 of 61 after CDX correction. Family selection must
run the **production parser on an archived capture**, not rank URL shapes by
cardinality — `shapes.py` did the latter and picked recipes, press releases, job
ads and FAQs. It is committed as a historical artifact; do not trust its ranking.

**Outstanding:** 398 prefix candidates sit at
`a8:~/gapwork/r10_out/slice_{0..7}.json`, derived from live URLs. They need one
CDX validation pass against the 123-crawl index cache **before** going into any
YAML.

---

## 9. Discovery mode (different cost profile)

Enumerate vs discover are opposite problems sharing one projection.

- The columnar index (Parquet via duckdb) unlocks keyword discovery.
- **Scan ccTLDs before generic TLDs** — `.com` is 42% of index space.
- **Rank by distinct TERMS, not paths**, and note term *count* ranks
  **backwards** (AUC 0.060); density (terms/n) is the real lever, with an n=20
  caveat.
- **Unit tokens beat keywords**, lifting the tripwire 1.24× → 9.25×. Prices are
  never in URLs; units survive CJK where keyword packs die.
- Path markers beat the keyword pack; recall 91.8%, ceiling 82.9% re-verified.
  Denominator is 585 hosts, not 623 files.
- CC mining **finds live sources**: 97% alive, 29% yield a price. But discovery
  has only covered 0.67% of the index and **rank does not predict yield**.

---

## 10. Checklist for the next sweep

1. `aws login` — the session expires; re-auth first.
2. Confirm no EC2 is already running and nothing is billing.
3. Confirm `misses-r8a/`, `misses-r8b/`, `misses-r9/` still in S3.
4. Fix parsers for the top-volume sources **before** the sweep (under-extraction
   does not self-heal).
5. CDX-validate the 398 pending prefixes; do not ship live-derived ones.
6. Resolve index-major, pin the crawl list to a file.
7. Fetch from S3 in us-east-1, one process per vCPU, scale by instance count.
8. Count non-200s separately from empty results, or you will record bans as
   "no data".
9. Instances self-terminate on tag `Project=cc-fetch`; verify none survive.
10. Pull results out of S3 — the account deletes data on 2027-02-27.
