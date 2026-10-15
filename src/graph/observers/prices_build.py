"""Build outputs of the observed week (`build_wNN/...`): one row per declared file or folder.

Used by `prices.build`, `prices.nonfood_global`, `prices.rtcal` and
`prices.typical_mass`. Braces in a declared path expand to one row each; rows come
from the parquet footer. A `promotion.json` carries its failed drift checks in `extra`.
Drift: a declared output that is not on disk.
"""

from __future__ import annotations

import json
from pathlib import Path

from graph import files
from graph.observe import mtime, parquet_rows, row, week, week_tag


def declared(node, suffixes: tuple[str, ...] = ()) -> list[Path]:
    out = []
    for p in node.paths:
        for g in files.data_globs(p["path"].replace("<wk>", week()).replace("wNN", week_tag())):
            if not suffixes or g.endswith(suffixes):
                out.append(Path(g))
    return out


def _extra(path: Path) -> dict:
    if path.name == "promotion.json":
        d = json.loads(path.read_text())
        return {"promoted": d.get("promoted"),
                "failed_checks": [c.get("check") for c in d.get("drift_checks", []) if not c.get("passed")]}
    return {"bytes": path.stat().st_size} if path.is_file() else {}


def observe(node) -> list[dict]:
    out = []
    for path in declared(node):
        exists = path.exists()
        out.append(row(node, f"{path.parent.name}/{path.name}", exists,
                       parquet_rows(path) if exists and path.suffix == ".parquet" else None,
                       mtime(path), drift=[] if exists else ["missing"],
                       extra=_extra(path) if exists else {}))
    return out
