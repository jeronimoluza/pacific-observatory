"""`prices.prepared`: `_prepared/.state.json` (country -> [[shard, mtime, size], ...]) vs
`_prepared/<r>/<s>/<c>.parquet`, one row per region/sub/country.

Drift: a state entry without its parquet, a parquet without a state entry, a recorded
shard whose mtime or size changed since (or that is gone), and a parquet more than a
day older than the state file -- not rewritten by the last prepare (bahamas, W42).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from graph.observe import mtime, node_path, parquet_rows, root_of, row, step_status

STALE_SECS = 24 * 3600


def _shard_changed(sig: list) -> bool:
    for path, recorded_mtime, size in sig:
        try:
            st = os.stat(path)
        except OSError:
            return True
        if st.st_mtime != recorded_mtime or st.st_size != size:
            return True
    return False


def observe(node) -> list[dict]:
    state_file = Path(node_path(node, "state", ".state.json"))
    root = root_of(node_path(node, "output", "_prepared/"))
    if not state_file.exists():
        return []
    state = json.loads(state_file.read_text())
    state_ts = mtime(state_file)
    on_disk = {str(p.relative_to(root))[: -len(".parquet")]: p for p in root.glob("*/*/*.parquet")}
    months = root.parent / f"{root.name}_months"
    sha = step_status("enrich")["sha"]
    out = []
    for key in sorted(set(state) | set(on_disk)):
        path = on_disk.get(key)
        ts = mtime(path) if path else None
        drift = []
        if key not in state:
            drift.append("not_in_state")
        elif _shard_changed(state[key]):
            drift.append("shard_changed_since_prepare")
        if path is None:
            drift.append("parquet_missing")
        elif ts < state_ts - STALE_SECS:
            drift.append("older_than_last_prepare")
        out.append(row(node, key, path is not None, parquet_rows(path) if path else None, ts, sha, drift,
                       {"shards": len(state.get(key, [])),
                        "months_parquet": (months / f"{key}.parquet").exists()}))
    return out
