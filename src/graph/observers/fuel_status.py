"""`fuel.publish`: one row per region from `data/fuel/_status/<region>.json`, which
`po fuel collect` and `po fuel publish` write. Drift: blocked publish, new source
failures, countries dropped since the last publish."""

from __future__ import annotations

import json
from pathlib import Path

from graph.observe import node_path, row


def observe(node) -> list[dict]:
    template = node_path(node, role="status")
    status_dir = Path(template).parent
    out = []
    for path in sorted(status_dir.glob("*.json")):
        st = json.loads(path.read_text(encoding="utf-8"))
        pub = st.get("publish") or {}
        drift = []
        if pub.get("status") == "blocked":
            drift.append("blocked: " + ",".join(pub.get("dropped_countries") or []))
        if pub.get("station_flags"):
            drift.append(f"station_flags: {len(pub['station_flags'])}")
        if pub.get("qa_jumps"):
            drift.append(f"qa_jumps: {len(pub['qa_jumps'])}")
        if pub.get("new_failures"):
            drift.append("new_failures: " + ",".join(pub["new_failures"]))
        last = st.get("last_published") or {}
        out.append(
            row(
                node,
                path.stem,
                pub.get("status") == "published",
                pub.get("countries_built", len(last.get("countries") or [])),
                pub.get("run_ts_utc") or last.get("run_ts_utc"),
                drift=drift,
                extra={
                    "color": pub.get("color"),
                    "status": pub.get("status"),
                    "failed_sources": len(pub.get("failed_sources") or []),
                    "seeded_only": not pub and bool(last.get("seeded")),
                },
            )
        )
    return out
