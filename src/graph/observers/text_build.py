"""Read-only status of the text build nodes, per owner (manifest ``owners``):

- ``text.counts``: one row per ``<cache>/<region>/<sub>/<country>/source_counts.params.json``;
  rows = sum of ``tails.n_rows``; extra carries what ``graph.checks.text_counts`` judges
  from the params alone (repeated ``source_set`` keys, keyword hash, newest ``last_date``);
- ``text.epu``: one row per ``<outputs>/<region>/<sub>/<country>/epu/epu.csv``; rows = lines
  minus the header; extra ``counts_utc`` = mtime of that country's params.json;
- ``text.dashboard``: one row per ``<dashboards>/<region>_policy_dashboard_fuel.html``;
  extra ``bytes``.

An owner whose root is not visible on this machine gives one row ``<owner>/_no_visible``;
a visible root with nothing in it ``<owner>/_vacio``; an owner without that root
``<owner>/_no_declarado``. Only file metadata and the
small params.json/epu.csv files are read.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

PARAMS = "source_counts.params.json"


def _empty(node, owner: str, name: str, base: Path | None) -> list[dict]:
    from graph.observe import row

    why = "_no_visible" if base is None or not base.exists() else "_vacio"
    return [row(node, f"{owner}/{why}", False, drift=[f"{name} {why[1:]}: {base}"], extra={"owner": owner})]


def _hash_ok(hashes: dict) -> bool | None:
    try:
        from graph.checks.text_counts import current_hashes

        return hashes == current_hashes(hashes)
    except Exception:  # noqa: BLE001 - the packs may not import on this machine
        return None


def counts(node, owner: str, cache: Path | None) -> list[dict]:
    from graph.observe import mtime, row

    files = sorted(cache.glob(f"*/*/*/{PARAMS}")) if cache and cache.is_dir() else []
    if not files:
        return _empty(node, owner, "cache", cache)
    out = []
    for pp in files:
        region, sub, country = pp.parent.relative_to(cache).parts
        p = json.loads(pp.read_text(encoding="utf-8"))
        tails = p.get("tails", {})
        last = max((t.get("last_date") or "" for t in tails.values()), default="") or None
        dup = {k: n for k, n in Counter(p.get("source_set", [])).items() if n > 1}
        out.append(row(node, f"{owner}/{region}/{sub}/{country}", True,
                       sum(t.get("n_rows") or 0 for t in tails.values()), mtime(pp),
                       extra={"owner": owner, "dup_keys": dup, "hash_ok": _hash_ok(p.get("keyword_hashes", {})),
                              "last_date": last, "n_sources": len(tails),
                              "schema_version": p.get("schema_version")}))
    return out


def epu(node, owner: str, outputs: Path | None, cache: Path | None) -> list[dict]:
    from graph.observe import iso, mtime, row

    files = sorted(outputs.glob("*/*/*/epu/epu.csv")) if outputs and outputs.is_dir() else []
    if not files:
        return _empty(node, owner, "outputs", outputs)
    out = []
    for f in files:
        region, sub, country = f.parents[1].relative_to(outputs).parts
        c = mtime(cache / region / sub / country / PARAMS) if cache else None
        with open(f, "rb") as fh:
            n = max(sum(1 for _ in fh) - 1, 0)
        out.append(row(node, f"{owner}/{region}/{sub}/{country}", True, n, mtime(f),
                       extra={"owner": owner, "counts_utc": iso(c) if c else None}))
    return out


def dashboards(node, owner: str, base: Path | None) -> list[dict]:
    from graph.observe import mtime, row

    files = sorted(base.glob("*_policy_dashboard_fuel.html")) if base and base.is_dir() else []
    if not files:
        return _empty(node, owner, "dashboards", base)
    return [row(node, f"{owner}/{f.name.split('_policy_')[0]}", True, None, mtime(f),
                extra={"owner": owner, "bytes": f.stat().st_size}) for f in files]


def observe(node) -> list[dict]:
    from graph.observe import row
    from graph.observers.text_owners import root

    need = {"text.counts": "cache", "text.epu": "outputs", "text.dashboard": "dashboards"}[node.id]
    out = []
    for owner, spec in (node.owners or {}).items():
        if not spec.get(need):
            out.append(row(node, f"{owner}/_no_declarado", False, drift=[f"{need} no declarado en owners.{owner}"],
                           extra={"owner": owner}))
        elif node.id == "text.counts":
            out += counts(node, owner, root(spec, "cache"))
        elif node.id == "text.epu":
            out += epu(node, owner, root(spec, "outputs"), root(spec, "cache"))
        elif node.id == "text.dashboard":
            out += dashboards(node, owner, root(spec, "dashboards"))
    return out
