"""`prices.stage_b`: `stage_b_wNN/<c>/report.txt` and `nonfood/report.txt`, one row per
country/scope, for the observed week.

Rows and trusted come from the report's first two lines; SHA is the week's `stageb`
step. Drift: a country folder without its report, and a report whose rows or trusted
differ from the footer of `observations.parquet` / `trusted_observations.parquet`.
"""

from __future__ import annotations

import re
from pathlib import Path

from graph.observe import mtime, node_path, parquet_rows, root_of, row, step_status

SCOPES = {"food": "", "nonfood": "nonfood"}
NUM = r"([\d,]+)"


def read_report(path: Path) -> dict:
    head = "\n".join(path.read_text(errors="replace").splitlines()[:3])
    out = {}
    for key, pat in (("rows", rf"^rows {NUM}"), ("product_months", rf"product-months {NUM}"),
                     ("products", rf"products {NUM}"), ("trusted", rf"^trusted {NUM}")):
        m = re.search(pat, head, re.M)
        out[key] = int(m.group(1).replace(",", "")) if m else None
    return out


def observe(node) -> list[dict]:
    root = root_of(node_path(node, "status", "report.txt"))
    if not root.is_dir():
        return []
    sha = step_status("stageb")["sha"]
    out = []
    for country_dir in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith(("_", "."))):
        for scope, sub in SCOPES.items():
            d = country_dir / sub if sub else country_dir
            report = d / "report.txt"
            if not d.is_dir():
                continue
            drift = []
            rep = read_report(report) if report.exists() else {}
            if not rep:
                drift.append("report_missing")
            obs = parquet_rows(d / "observations.parquet")
            trusted = parquet_rows(d / "trusted_observations.parquet")
            if rep and obs is not None and rep["rows"] != obs:
                drift.append(f"rows: report {rep['rows']} != parquet {obs}")
            if rep and trusted is not None and rep["trusted"] != trusted:
                drift.append(f"trusted: report {rep['trusted']} != parquet {trusted}")
            out.append(row(node, f"{country_dir.name}/{scope}", bool(rep), rep.get("rows"), mtime(report),
                           sha, drift, {**rep, "obs_parquet_rows": obs, "trusted_parquet_rows": trusted}))
    return out
