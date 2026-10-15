"""`prices.classified`: `decisions_hierlex/_decide.jsonl` (one line per classify run, append
only) vs the per-country decision and classified parquets, one row per country.

The newest line naming a country is its state: rows = `decisions`, SHA = `git_head`.
Drift: a country in the ledger without its parquets, a decisions parquet without a
ledger line, and a decisions parquet whose footer row count != the ledger's `decisions`.
"""

from __future__ import annotations

import json
from pathlib import Path

from graph.observe import mtime, node_path, parquet_rows, root_of, row


def observe(node) -> list[dict]:
    ledger = Path(node_path(node, "ledger", "_decide.jsonl"))
    cache = root_of(node_path(node, "output", "decisions_hierlex"))
    decisions_dir, classified_dir = cache / "decisions_hierlex", cache / "classified_hierlex"
    last: dict[str, dict] = {}
    if ledger.exists():
        for line in ledger.read_text().splitlines():
            if line.strip():
                e = json.loads(line)
                for c in e.get("countries", []):
                    last[c] = e
    on_disk = {p.stem for p in decisions_dir.glob("*.parquet")}
    out = []
    for c in sorted(set(last) | on_disk):
        e = last.get(c)
        dec = decisions_dir / f"{c}.parquet"
        n = parquet_rows(dec) if c in on_disk else None
        drift = []
        if e is None:
            drift.append("not_in_ledger")
        if c not in on_disk:
            drift.append("decisions_missing")
        if not (classified_dir / f"{c}.parquet").exists():
            drift.append("classified_missing")
        multi = e is not None and len(e.get("countries", [])) > 1
        if e is not None and n is not None and not multi and n != e.get("decisions"):
            drift.append(f"decisions_rows: ledger {e.get('decisions')} != parquet {n}")
        extra = {k: e.get(k) for k in ("bundle", "tau", "policy", "classified", "states")} if e else {}
        out.append(row(node, c, e is not None and c in on_disk,
                       e.get("decisions") if e and not multi else n,
                       e["written_at"] if e else mtime(dec), (e or {}).get("git_head", "")[:12] or None,
                       drift, {**extra, "parquet_rows": n}))
    return out
