# a8 side of the refresh

a8 collects; the Mac merges. SSKJL is not needed on a8.

- A systemd timer runs `scripts/staged_collect_all.sh` Mon and Fri 06:00 UTC from the repo on a8.
- Output: `~/text_staging/<run_id>/<region>/...` plus `STATUS.md`, `driver.log`, `events_<region>.log`. A flock on `~/text_staging/.lock` prevents overlapping runs (exclude `.lock` when rsyncing).
- Ledgers: `~/text_state/<region>.sqlite`. a8 dedups against its ledger plus its own unmerged staging. A region with no ledger is SKIPPED in STATUS.
- Defaults: P=24 parallel sources, 300 s per source, abort below `MIN_FREE_GB` (5) free; `REGIONS` env restricts regions.
- a8 is headless: stage a self-reverting fallback before changing its network or timer config.

## First-time setup (once per region)

On the Mac, where SSKJL holds the history:
```bash
poetry run po text ledger-bootstrap --region <r>   # builds ~/text_state/<r>.sqlite from SSKJL
rsync -t ~/text_state/<r>.sqlite a8:~/text_state/
```
Without the bootstrap a8 has no ledger and skips the region. After each Mac merge the ledger is pushed back (SKILL step 2); the Mac copy is master.
