"""`prices.raw`: the week's collect ledgers (`status.jsonl`), one row per country/source.

The week's ledgers are the comma-separated paths in `<logs>/<wk>/ledger_path`, in run
order; a later ledger's status for a source replaces an earlier one and `new_rows` add
up. A ledger named there but gone from disk is drift (W41's was deleted). The
`_week` row carries the `STATUS` line.
"""

from __future__ import annotations

import json
from pathlib import Path

from graph.observe import iso, mtime, node_path, root_of, row

DONE_STATUSES = {"ok", "ok_norows"}


def observe(node) -> list[dict]:
    week_dir = root_of(node_path(node, "status", "STATUS"))
    if not week_dir.is_dir():
        return []
    status_file = week_dir / "STATUS"
    status = status_file.read_text().strip() if status_file.exists() else None
    ledger_list = week_dir / "ledger_path"
    ledgers = [Path(p) for p in ledger_list.read_text().strip().split(",") if p] if ledger_list.exists() else []
    week_drift = [] if ledgers else ["no_ledger_path"]
    by_source: dict[str, dict] = {}
    for ledger in ledgers:
        ts = mtime(ledger)
        if ts is None:
            week_drift.append(f"ledger_missing: {ledger}")
            continue
        for line in ledger.read_text().splitlines():
            if not line.strip():
                continue
            e = json.loads(line)
            s = by_source.setdefault(f"{e['region']}/{e['country']}/{e['source']}", {"rows": 0, "runs": 0})
            s["rows"] += e.get("new_rows") or 0
            s["runs"] += 1
            s.update(status=e.get("status"), rc=e.get("rc"), secs=e.get("secs"), ts=ts, ledger=ledger.parent.name)
    rows = [row(node, "_week", bool(status and " DONE " in f" {status} "), freshness=mtime(status_file),
                drift=week_drift, extra={"STATUS": status, "ledgers": [str(p) for p in ledgers]})]
    for key, s in sorted(by_source.items()):
        rows.append(row(node, key, s["status"] in DONE_STATUSES, s["rows"], iso(s["ts"]),
                        extra={k: s[k] for k in ("status", "rc", "secs", "runs", "ledger")}))
    return rows
