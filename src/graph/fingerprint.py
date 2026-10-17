"""Code fingerprint per node: what would make the node's output stale if it changed.

A node's own hash covers the content of its code files (or `fingerprint.code`
when the manifest narrows them), its config files, the installed version of
each declared dependency, its `params`, and `fingerprint.reuse` -- a function
that already fingerprints the stage (Stage B reuses
`extraction.code_fingerprint()`). The node's fingerprint then folds in the
fingerprints of its inputs, so a regex edit restales Stage B and everything
below it, and nothing above.

Content, not mtime: a fresh checkout of the same SHA gives the same value.
"""

from __future__ import annotations

import hashlib
import importlib
import json
from importlib import metadata

from graph import files
from graph.manifest import REPO_ROOT, Node, topo_order


def _dep_versions(deps: list[str]) -> tuple[dict[str, str | None], list[str]]:
    versions, warnings = {}, []
    for dep in deps:
        name, _, pin = dep.partition("==")
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = None
        if pin and versions[name] != pin:
            warnings.append(f"{name} instalado {versions[name]} != {pin}")
    return versions, warnings


def own_hash(node: Node) -> dict:
    fp = node.fingerprint
    h = hashlib.sha256()
    missing = []
    paths = set()
    for g in (fp.get("code") or node.code_paths) + fp.get("config", []):
        hits = files.repo_files(g)
        if not hits:
            missing.append(g)
        paths.update(hits)
    for rel in sorted(paths):
        h.update(rel.encode())
        h.update((REPO_ROOT / rel).read_bytes())
    versions, warnings = _dep_versions(fp.get("deps", []))
    h.update(json.dumps(versions, sort_keys=True).encode())
    h.update(json.dumps(fp.get("params", {}), sort_keys=True).encode())
    reused = None
    if fp.get("reuse"):
        module, func = fp["reuse"].split(":")
        reused = getattr(importlib.import_module(module), func)()
        h.update(str(reused).encode())
    h.update(json.dumps(missing).encode())
    return {
        "own": h.hexdigest()[:16],
        "n_files": len(paths),
        "deps": versions,
        "reuse": reused,
        "missing": missing,
        "warnings": warnings,
    }


def fingerprints(nodes: dict[str, Node]) -> dict[str, dict]:
    """{node: own-hash detail + `fingerprint`, which includes every upstream node}."""
    order, cycles = topo_order(nodes)
    if cycles:
        raise ValueError(f"el grafo tiene ciclos: {cycles}")
    out = {}
    for nid in order:
        detail = own_hash(nodes[nid])
        h = hashlib.sha256(detail["own"].encode())
        for dep in sorted(nodes[nid].inputs):
            h.update(f"{dep}={out[dep]['fingerprint']}".encode())
        detail["fingerprint"] = h.hexdigest()[:16]
        out[nid] = detail
    return out
