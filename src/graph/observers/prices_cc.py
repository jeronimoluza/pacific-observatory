"""`prices.raw_cc`: `_cc_ledger/ledger.parquet` (one row per source × crawl), one row per source.

Rolling, not weekly. A source the ledger says was parsed but with no
`common_crawl_data/items` folder under any country on disk is drift.
"""

from __future__ import annotations

import glob
from collections import Counter
from pathlib import Path

from graph.observe import iso, mtime, node_path, root_of, row


def observe(node) -> list[dict]:
    import pyarrow.parquet as pq

    ledger = Path(node_path(node, "ledger", "_cc_ledger"))
    if not ledger.exists():
        return []
    t = pq.read_table(ledger, columns=["source", "status", "rows", "ts"]).to_pylist()
    items_root = root_of(node_path(node, "output", "common_crawl_data"))
    on_disk = {
        Path(p).parent.name: str(Path(p).parent.relative_to(items_root))
        for p in glob.glob(str(items_root / "*/*/*/*/common_crawl_data"))
    }
    by_source: dict[str, dict] = {}
    for r in t:
        s = by_source.setdefault(
            r["source"], {"rows": 0, "crawls": 0, "status": Counter(), "ts": None}
        )
        s["rows"] += r["rows"] or 0
        s["crawls"] += 1
        s["status"][r["status"]] += 1
        ts = str(r["ts"]) if r["ts"] is not None else None
        if ts and (s["ts"] is None or ts > s["ts"]):
            s["ts"] = ts
    out = []
    for source, s in sorted(by_source.items()):
        drift = (
            ["parsed_without_items_dir"]
            if s["status"].get("parsed") and source not in on_disk
            else []
        )
        out.append(
            row(
                node,
                on_disk.get(source, source),
                bool(s["status"].get("parsed")),
                s["rows"],
                s["ts"],
                drift=drift,
                extra={
                    "crawls": s["crawls"],
                    "status": dict(s["status"]),
                    "ledger_mtime": iso(mtime(ledger)),
                },
            )
        )
    return out
