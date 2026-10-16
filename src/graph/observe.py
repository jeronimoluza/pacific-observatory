"""Shared plumbing for observers: the week being observed, node paths, and the runner.

An observer is `src/graph/observers/<name>.py` exposing `observe(node) -> list[dict]`,
read-only, one row per partition with the keys in `ROW_KEYS`. pandas/pyarrow are
imported inside functions, never at module level.

The week is `PO_GRAPH_WEEK` (`2026-W42`), default the current ISO week UTC. It fills
`<wk>` (`2026-W42`) and `wNN` (`w42`) in manifest paths; rolling trees ignore it.
"""

from __future__ import annotations

import importlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from graph.manifest import Node

ROW_KEYS = (
    "node",
    "partition",
    "done",
    "rows",
    "freshness_utc",
    "sha",
    "drift",
    "extra",
)
LOGS_ROOT = Path.home() / "po" / "logs" / "weekly"


def week() -> str:
    return os.environ.get("PO_GRAPH_WEEK") or datetime.now(timezone.utc).strftime(
        "%G-W%V"
    )


def week_tag() -> str:
    return "w" + week().split("-W")[1]


def row(
    node: Node,
    partition: str,
    done: bool,
    rows: int | None = None,
    freshness=None,
    sha: str | None = None,
    drift: list[str] | None = None,
    extra: dict | None = None,
) -> dict:
    if isinstance(freshness, (int, float)):
        freshness = iso(freshness)
    elif freshness:
        try:
            dt = datetime.fromisoformat(str(freshness).replace("Z", "+00:00"))
            freshness = iso(
                (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).timestamp()
            )
        except ValueError:
            freshness = str(freshness)
    return {
        "node": node.id,
        "partition": partition,
        "done": done,
        "rows": rows,
        "freshness_utc": freshness,
        "sha": sha,
        "drift": drift or [],
        "extra": extra or {},
    }


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def mtime(path: Path) -> float | None:
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def node_path(node: Node, role: str = "output", contains: str = "") -> str | None:
    """The first declared path of `role` containing `contains`, with `~` and the week
    filled in; other `<x>` placeholders are left for the observer."""
    for p in node.paths:
        if p.get("role", "output") == role and contains in p["path"]:
            path = p["path"].replace("<wk>", week()).replace("wNN", week_tag())
            return os.path.expanduser(path)
    return None


def root_of(template: str) -> Path:
    """The directory before the first placeholder or glob in `template`."""
    cut = re.search(r"[<*{]", template)
    head = template[: cut.start()] if cut else template
    return Path(head if head.endswith("/") or not cut else head.rsplit("/", 1)[0])


def parquet_rows(path: Path) -> int | None:
    """Row count from the parquet footer; no row is read."""
    import pyarrow.parquet as pq

    try:
        return pq.read_metadata(path).num_rows
    except (OSError, ValueError):
        return None


def step_status(step: str) -> dict:
    """`STATUS_<step>` of the week (state, ts) and the last `@sha` that step logged."""
    week_dir = LOGS_ROOT / week()
    out = {"step": step, "state": None, "ts": None, "sha": None}
    status = week_dir / f"STATUS_{step}"
    if status.exists():
        parts = status.read_text().split(maxsplit=2)
        out["ts"], out["state"] = parts[0], parts[1] if len(parts) > 1 else None
    events = week_dir / "events.log"
    if events.exists():
        for line in events.read_text(errors="replace").splitlines():
            m = re.search(rf"\s{re.escape(step)}: .*@([0-9a-f]{{7,40}})", line)
            if m:
                out["sha"] = m.group(1)
    return out


def observe(node: Node) -> list[dict]:
    """Run the node's observer; an observer that raises gives one row naming the error."""
    if not node.observer:
        return []
    try:
        mod = importlib.import_module(f"graph.observers.{node.observer}")
        rows = mod.observe(node)
    except Exception as e:  # noqa: BLE001 - one broken observer must not hide the others
        return [
            row(
                node,
                "_observer",
                False,
                drift=[f"observer_error: {type(e).__name__}: {e}"],
            )
        ]
    for r in rows:
        r.setdefault("node", node.id)
        r.setdefault("drift", [])
        r.setdefault("extra", {})
    return json.loads(json.dumps(rows, default=str))
