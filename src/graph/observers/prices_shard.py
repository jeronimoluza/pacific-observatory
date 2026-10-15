"""`prices.shard`: `raw/.state.json` (source -> [newest raw mtime, raw file count]) vs
the per-source shards on disk, one row per region/sub/country/source.

Drift: a state entry without its shard, a shard without a state entry, and a shard
older than the newest raw file the state recorded for it. Rows come from the
shard's parquet footer.
"""

from __future__ import annotations

import json
from pathlib import Path

from graph.observe import iso, mtime, node_path, parquet_rows, root_of, row, step_status


def observe(node) -> list[dict]:
    state_file = Path(node_path(node, "state", ".state.json"))
    shard_root = root_of(node_path(node, "output", "_per_source"))
    if not state_file.exists():
        return []
    state = json.loads(state_file.read_text())
    on_disk = {str(p.relative_to(shard_root))[: -len(".parquet")]: p for p in shard_root.glob("*/*/*/*.parquet")}
    sha = step_status("enrich")["sha"]
    out = []
    for key in sorted(set(state) | set(on_disk)):
        shard = on_disk.get(key)
        sig = state.get(key)
        drift = []
        if sig is None:
            drift.append("not_in_state")
        if shard is None:
            drift.append("shard_missing")
        ts = mtime(shard) if shard else None
        if sig and ts is not None and ts < sig[0]:
            drift.append("shard_older_than_raw")
        extra = {"raw_newest": iso(sig[0]), "raw_files": sig[1]} if sig else {}
        out.append(row(node, key, shard is not None, parquet_rows(shard) if shard else None, ts,
                       sha, drift, extra))
    return out
