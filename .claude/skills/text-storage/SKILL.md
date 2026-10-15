---
name: text-storage
description: "Manage two-tier text-pipeline storage between the repo's `data/text/` and the SSKJL external drive (`/Volumes/SSKJL/data/text/`). Use whenever the user wants to free local disk by archiving a country/region to the drive, restore data from the drive for calculations, or check what is local vs on the drive — phrases like 'what's on the drive', 'should I archive X', 'free up space', 'back up <country>', 'restore <country>', 'what should I restore', 'is <country> on the drive', 'I need disk space', 'pull <country> back', 'move <country> to the drive', 'is the drive in sync', 'do I need to bring <country> back before building'. Also use even when the request is implicit, e.g. the user says they're running low on disk while collecting, or asks whether it's safe to delete `data/text/<country>/`. Always run `python run.py text storage-status` first to see ground truth, then archive/restore/suggest based on the result. Never execute `rm` — always print it as a copy-paste command for the user to run."
---

# Text Storage Tier Manager

The text pipeline collects gigabytes of news per country and the laptop's local
disk is the bottleneck. The user keeps a tier-2 store on the SSKJL external
drive at `/Volumes/SSKJL/data/text/` that mirrors the repo's `data/text/` layout
(`<region>/<subregion>/<country>/<source>/`). This skill is the orchestrator
for moving data between those two tiers safely.

## What this skill does

Three things, in this order:

1. **Inspect** what's local vs on the drive (`python run.py text storage-status`)
2. **Decide** what to do per the state machine below
3. **Execute** archive/restore commands when the user's intent is clear, or
   suggest the exact command when intent is broad

It does NOT run `rm`. Ever. The drive is the user's safety net — pruning local
copies is a manual step gated by the user, not the assistant.

## The boundary that does not move

**Execute freely:** `python run.py text storage-status`,
`python run.py text archive`, `python run.py text restore`. These are
non-destructive — `archive` and `restore` use rsync without `--delete` and
verify after copying.

**Never execute:** `rm`, `rm -rf`, `find ... -delete`, or any other deletion
of `data/text/`. When the suggested workflow ends in a deletion, print the
exact `rm -rf <paths>` command for the user to run themselves and stop. This
is the user's gate, not yours.

If the user explicitly asks you to run rm (e.g. "go ahead and delete it"),
print the command and remind them to paste it in themselves. The constraint
is structural, not advisory.

## Storage layout (for reference)

```
Local:  data/text/<region>/<subregion>/<country>/<source>/{news.csv, urls.csv, metadata/, failed/, ...}
Drive:  /Volumes/SSKJL/data/text/<region>/<subregion>/<country>/<source>/{...}
```

Drive layout matches the canonical `src/configs/regions.yaml` taxonomy.
Legacy `eap2/` (with old slugs `lao`, `pacific`) is grandfathered on the
drive — don't try to "fix" it. New work under `eap/` uses canonical slugs.

## Procedure

### Step 1: Always run `storage-status` first

Don't guess. The CLI walks both trees and gives you the ground truth.

```bash
python run.py text storage-status [scope flags]
```

Scope flags for `storage-status`:
`--region eap | -S pacific_islands | --country fiji`.
Without flags, it scans everything. Note: `storage-status` itself does not
take `--source` — it aggregates per-country. Drill into a single source
with `--country` and read the table.

If the drive isn't mounted, `storage-status` still works on the local side,
the drive column reads `(offline)`, and each row's state gets a `?` suffix
(e.g., `local-only?`) — meaning "locally we know X, but we couldn't confirm
the drive side". Tell the user the drive is unmounted and stop — `archive`
and `restore` will hard-fail until they remount it.

### Step 2: Read the state machine

`storage-status` aggregates state per country (across all news.csv under
that country dir). Every row has one of these states:

| State | Meaning | Action |
|---|---|---|
| `local-only` | Exists locally, not on drive | `archive` |
| `drive-only` | Exists on drive, not locally | `restore` |
| `both-equal` | Row counts match on every news.csv | safe to `rm` (print, don't run) |
| `local-newer` | Some local news.csv has more rows than drive | `archive` |
| `drive-newer` | Some drive news.csv has more rows than local | `restore` (unusual — flag to user) |
| `mismatch` | Counts differ both ways — local has rows the drive doesn't AND vice versa | manual review, do nothing |

`mismatch` and `drive-newer` are red flags. Surface them to the user
before doing anything else; do not try to "resolve" them silently with
rsync — the user's collect/archive/restore sequence is what creates these
states and they need to know.

### Step 3: Decide — execute or suggest

Two modes based on how specific the user's intent is.

**Execute mode** — user named a target. Examples that fall here:
- "back up Saudi Arabia to the drive"
- "archive the gulf states"
- "restore Fiji"
- "I'm done collecting kenya, move it"

Run the matching command directly:

```bash
python run.py text archive --country <slug>
python run.py text restore --country <slug>
python run.py text archive --region menaap
python run.py text archive --subregion gulf_states
```

The CLI verifies after rsync (size match per file + news.csv row counts).
If verify fails, the CLI exits non-zero and prints which files failed —
relay that to the user verbatim, do NOT print the rm hint.

**Suggest mode** — user is broader. Examples that fall here:
- "what should I do about the gulf states?"
- "I'm running low on disk, what's safe to free?"
- "what's drifted between the two sides?"

Group the `storage-status` rows by suggested action and write out the
exact commands the user would run. Don't pick for them.

### Step 4: Print the rm hint (never execute it)

After a successful `archive`, the CLI itself prints the rm hint. Pass it
through verbatim and add a short explainer that the command is the user's
to run. The CLI's actual output looks like:

```
  ✓ Archived country=saudi_arabia — 24 files, 1.4 GB, 24 news.csv verified.

  To free local space, run:
    rm -rf data/text/menaap/gulf_states/saudi_arabia
```

If the verify step fails, the CLI prints `✗ Archive verification FAILED`
plus the list of mismatched files and ends with `No rm hint — local data
is NOT safe to delete.` In that case, surface the failure to the user and
stop — do not try to "manually" issue an rm.

After `restore`, there's no rm hint at all (drive is canonical, local is
scratch). If `restore`'s verify finds local files the drive doesn't have,
the CLI prints a `⚠ Local has data the drive doesn't — re-archive before
pruning:` warning. Tell the user to run `archive` before any further
restore-then-delete cycle on that scope.

## Useful flags

- `--news-only` (archive only) — copies just `news.csv` and `urls.csv`,
  skipping `metadata/`, `failed/`, etc. Cheap update for a country that
  was already archived once and just got a few more rows. Default
  `archive` syncs the full source directory.
- `--path P` — scope by raw path instead of region/country flags. Useful
  for one-off cases like "archive everything under `data/text/eap/east_asia/japan/japan_news/`".
- `--json` (storage-status only) — machine-readable output. Use this if
  you need to programmatically pick a subset (e.g. "all `local-only`
  rows in eap").

## Common workflows

### "I'm done collecting <country>, free up space"

1. `python run.py text storage-status --country <slug>` — confirm state.
2. If `local-only` or `local-newer`: `python run.py text archive --country <slug>`.
3. Pass the CLI's verified rm hint to the user. Stop.

### "I need to build EPU for <country> and the data isn't local"

1. `python run.py text storage-status --country <slug>` — should show `drive-only`.
2. `python run.py text restore --country <slug>`.
3. After it verifies, the user can run `python run.py text build --country <slug>`.
   You can offer to run it for them; don't run it pre-emptively.

### "Is the drive in sync with my repo?"

1. `python run.py text storage-status [scope]`.
2. Summarize: how many countries are `both-equal`, how many have drift,
   which ones (with the suggested command per row).
3. Don't run anything. This is a status query, not an action.

### "What's safe to delete locally?"

1. `python run.py text storage-status [scope]`.
2. Filter to `both-equal` rows.
3. Print the rm command for those paths, grouped sensibly. User runs it.

## Failure modes to recognize

- **Drive not mounted.** `archive` and `restore` will exit non-zero with
  a clear message. Don't retry — tell the user to remount SSKJL via Disk
  Utility (default mountpoint is `/Volumes/SSKJL`).
- **Verify fails after archive.** The CLI prints which files failed.
  Don't print the rm hint. Re-run archive once; if it fails again, surface
  to the user as something requiring manual review (likely full drive or
  filesystem error).
- **`mismatch` state.** Both sides have rows the other doesn't. Don't
  rsync either way blindly. Ask the user which side they trust. Most
  likely cause: a partial archive ran while a collect was still writing
  on the same country. The fix is usually to finish the collect, then
  archive the merged local copy.
- **User wants to delete before archive verifies.** Refuse politely.
  Print the archive command first, wait for it to succeed, then print the
  rm hint. The whole point of the verify step is that it gates the rm.

## What this skill explicitly does not do

- Real-time CSV writes to the drive during collect. The drive is for
  archive/restore boundaries, not the hot path.
- Compression, encryption, manifests, scheduled syncs, multi-drive
  support, cloud tier. All explicitly out of scope per the design.
- Recover from `rm -rf data/text/<country>/` when the drive copy was
  incomplete. The `archive` verify step is what prevents this — if the
  user runs rm without verifying first, that's on them.
