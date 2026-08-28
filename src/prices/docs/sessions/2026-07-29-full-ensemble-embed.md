# 2026-07-29 — Full ensemble embed (0.6B + 4B + 8B) of the F&B survivors

## Goal

Bank the full **7,680-d ensemble embedding** (Qwen3-Embedding 0.6B + 4B + 8B-q8,
each block L2-normed then concatenated) for every one of the **381,228 F&B
pre-filter survivors** ([[2026-07-28-fnb-prefilter-bakeoff]]), so the logistic
head can be trained/swapped/re-scored **without ever re-embedding**. The embed is
the expensive, stable part; the head is cheap and changes often. Constraint: it
must fit a **16 GB Mac** (the 8B-q8 weights alone are ~7.5 GB) and be **resumable**
across interruptions.

## Method — block-outer, one model resident at a time

The embed ran **one block at a time** (block-outer), never co-resident, so peak
RAM ≈ the single heaviest worker rather than the sum. Each block streamed its
vectors into the durable store (`classifier/embed_store.py`) as it went:

- **Store layout:** `data/prices/enrich/_embed_store/<tag>/bucket_<b>.npz`, 256
  name-hash buckets per tag, `keys` (names) + `mat` (fp16). A name hashes to a
  fixed bucket stable across corpus versions; `append()` writes each bucket
  **atomically after** the encode returns (`.npz.tmp` → `replace`), so a kill
  mid-encode never corrupts a bucket.
- **Resume:** `embed_store.missing(tag, buckets_for(names))` returns only the
  not-yet-embedded names, so a relaunch skips banked buckets.
- **Drivers** (job-tmp, regenerable — the durable path is
  `batch_embed._build_store`): `embed_0p6b_only.py` (in-process sentence-
  transformers via `embedding.encode_st_block`), `embed_4b_only.py` and
  `embed_8b_only.py` (both through the long-lived `embedding.MlxWorker` —
  a `.venv_mlx --serve` subprocess that loads one mlx model once and embeds
  successive chunks over stdin).

## Result — all three tags banked and aligned, ≈17.5h total

| Tag | Backend | Dim | Wall clock | Steady rate | Store size |
|---|---|---|---|---|---|
| `0p6b` | sentence-transformers (in-proc) | 1024 | ~2h 04m | ~51 names/s | 996 MB |
| `4b` | mlx `MlxWorker` (seq 176) | 2560 | ~3h 38m | ~25 names/s | 2.1 GB |
| `8b_q8` | mlx `MlxWorker` solo (seq 176) | 4096 | ~11.5h | ~9–12 names/s | 3.2 GB |

- **Each tag holds exactly 381,228 vectors** across 256/256 buckets — verified by
  direct npz count, not by log-scraping. The full 7,680-d ensemble is aligned and
  ready for the head.
- **No OOM even for 8B-q8** — running it solo (nothing else heavy resident) fit
  16 GB comfortably. 0.6B and 4B alone kept the Mac usable throughout.
- **8B ran across two user-requested pauses** (stop/resume ×2). Every resume
  correctly reported the shrinking `missing` set and skipped banked buckets;
  atomic append gave **zero corruption** across the pauses. One ~40-min throughput
  stall on a single bucket (resource contention / thermal) recovered on its own.
- Aggregate embed compute ≈ **~17.5h** (2h04 + 3h38 + ~11.5h), spanning the night
  of 2026-07-28 into 2026-07-29.

## Gotcha corrected — the phantom "0.6B short ~3k names"

Across the 4B/8B completion reports I repeatedly claimed the `0p6b` tag was banked
on an older **378,264-name** set and needed a ~3k top-up before the concat. This
was **wrong**. `products_input.parquet` is a single fixed snapshot (2,007,881 rows
/ 1,585,556 unique names, scrape span 2026-05-15 → 2026-07-27); it never grew
between runs. The 378,264 was the 0.6B DONE-log's *embedded-this-run* count (names
missing at that launch), **not** the store total — pre-existing proof buckets made
it finish at the full set. Direct check: `missing("0p6b", current_survivors) == 0`,
and all three tags hold 381,228. **Lesson: judge completeness from the actual npz
store totals, never from a DONE-log's embedded count.**

## Artifacts

- `data/prices/enrich/_embed_store/{0p6b,4b,8b_q8}/bucket_*.npz` — the durable
  fp16 stores (the deliverable of this session).
- Job-tmp drivers `embed_0p6b_only.py` / `embed_4b_only.py` / `embed_8b_only.py`
  (ephemeral; regenerable from `batch_embed._build_store`).

Full detail in memory `prices_0p6b_full_embed_banked_20260728`.

## Next session

Write `classified.parquet` — the head-scoring pass over the banked stores.
Because the ensemble is fully banked, the build phase is a no-op and classify
resumes straight into predict. (→ [[2026-07-29-classify-and-downstream-exploration]])

## Notes / gotchas

- Work done **in place** (worktrees off; `src/prices/` isn't on `main`).
- The block-outer **solo** approach is what makes the 8B-q8 tractable on 16 GB —
  do not co-resident the mlx workers.
- Prior-session uncommitted edits still present, untouched: `config.py`
  (4B/8B seq 512→176) and `embedding_mlx.py` (length-sort in `_embed`) — the MLX
  wall-clock speedup lever these rates already reflect.
