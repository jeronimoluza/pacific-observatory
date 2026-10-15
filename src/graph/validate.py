"""`graph validate`: the manifests are a DAG and everything they name exists.

Reads only the manifests and the repo (git trees or the working tree); it never
opens data. `check_paths` is the one exception that touches data paths, and
only globs for a first hit.
"""

from __future__ import annotations

from pathlib import Path

from graph import files
from graph.manifest import MANIFEST_DIR, REPO_ROOT, Node, load, topo_order


def _module_file(module: str) -> Path:
    return REPO_ROOT / "src" / (module.replace(".", "/") + ".py")


def validate(manifest_dir: Path = MANIFEST_DIR, rev: str | None = None) -> tuple[dict[str, Node], list[str], list[str]]:
    """(nodes, errors, warnings). `rev` overrides every node's `code_ref`."""
    nodes, errors = load(manifest_dir)
    warnings: list[str] = []
    for nid, node in sorted(nodes.items()):
        errors += [f"{nid}: input {i!r} no es un nodo" for i in node.inputs if i not in nodes]
        ref = rev or node.code_ref
        if ref and not files.ref_exists(ref):
            warnings.append(f"{nid}: ref {ref!r} no existe en este repo; code_paths sin chequear")
            continue
        where = ref or "working tree"
        globs = node.code_paths + node.fingerprint.get("code", []) + node.fingerprint.get("config", [])
        errors += [f"{nid}: {g!r} no encuentra archivos en {where}" for g in globs if not files.repo_files(g, ref)]
        reuse = node.fingerprint.get("reuse")
        if reuse and not files.repo_files(str(_module_file(reuse.split(":")[0]).relative_to(REPO_ROOT)), ref):
            errors.append(f"{nid}: fingerprint.reuse {reuse!r} no existe en {where}")
        if node.observer and not (Path(__file__).parent / "observers" / f"{node.observer}.py").is_file():
            errors.append(f"{nid}: observer {node.observer!r} no existe en src/graph/observers/")
    _, cycles = topo_order(nodes)
    errors += [f"ciclo: {c}" for c in cycles]
    return nodes, errors, warnings


def check_paths(nodes: dict[str, Node], machine: str) -> list[tuple[str, str, str | None]]:
    """(node, glob, first hit or None) for every data glob declared on `machine`."""
    out = []
    for nid, node in sorted(nodes.items()):
        for p in node.paths:
            if p.get("machine") == machine:
                out += [(nid, g, files.first_match(g)) for g in files.data_globs(p["path"])]
    return out
