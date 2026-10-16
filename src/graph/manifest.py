"""Asset manifests: one YAML per pipeline under `src/graph/manifests/`.

A manifest declares what should exist (nodes, their code, inputs, outputs and
checks); observers say what does exist. Node ids are global across manifests,
so a text node can be the input of a prices node and the other way round.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIR = Path(__file__).resolve().parent / "manifests"

ESTADOS = ("prod", "dev", "humano", "fuera_mvp")
MACHINES = ("a8", "mac")
ROLES = ("output", "state", "ledger", "status")
COLORS = ("rojo", "amarillo")

NODE_KEYS = {
    "estado",
    "desc",
    "code_ref",
    "code_paths",
    "code_external",
    "run",
    "paths",
    "inputs",
    "external_inputs",
    "partition",
    "fingerprint",
    "freshness",
    "checks",
    "observer",
}
FINGERPRINT_KEYS = {"code", "config", "deps", "params", "reuse", "note"}
PATH_KEYS = {"path", "machine", "role"}
CHECK_KEYS = {"desc", "color"}


@dataclass
class Node:
    id: str
    pipeline: str
    estado: str
    code_ref: str | None = None
    code_paths: list[str] = field(default_factory=list)
    inputs: list[str] = field(default_factory=list)
    paths: list[dict] = field(default_factory=list)
    fingerprint: dict = field(default_factory=dict)
    checks: list[dict] = field(default_factory=list)
    observer: str | None = None
    raw: dict = field(default_factory=dict)


def _schema_errors(nid: str, spec) -> list[str]:
    if not isinstance(spec, dict):
        return [f"{nid}: el nodo no es un mapping"]
    errs = [f"{nid}: clave desconocida {k!r}" for k in sorted(set(spec) - NODE_KEYS)]
    if spec.get("estado") not in ESTADOS:
        errs.append(f"{nid}: estado {spec.get('estado')!r} no está en {ESTADOS}")
    for key in (
        "code_paths",
        "code_external",
        "inputs",
        "external_inputs",
        "paths",
        "checks",
    ):
        if key in spec and not isinstance(spec[key], list):
            errs.append(f"{nid}: {key} debe ser lista")
    fp = spec.get("fingerprint", {})
    if not isinstance(fp, dict):
        errs.append(f"{nid}: fingerprint debe ser mapping")
    else:
        errs += [
            f"{nid}: fingerprint.{k} desconocida"
            for k in sorted(set(fp) - FINGERPRINT_KEYS)
        ]
        if fp.get("reuse") and not re.fullmatch(r"[\w.]+:\w+", fp["reuse"]):
            errs.append(f"{nid}: fingerprint.reuse debe ser 'modulo:funcion'")
    for p in spec.get("paths", []) if isinstance(spec.get("paths"), list) else []:
        if not isinstance(p, dict) or set(p) - PATH_KEYS or "path" not in p:
            errs.append(f"{nid}: path mal formado {p!r}")
        elif p.get("machine") not in MACHINES or p.get("role", "output") not in ROLES:
            errs.append(f"{nid}: machine/role inválido en {p['path']!r}")
    for c in spec.get("checks", []) if isinstance(spec.get("checks"), list) else []:
        if (
            not isinstance(c, dict)
            or set(c) - CHECK_KEYS
            or c.get("color") not in COLORS
        ):
            errs.append(f"{nid}: check mal formado {c!r}")
    return errs


def load(manifest_dir: Path = MANIFEST_DIR) -> tuple[dict[str, Node], list[str]]:
    """All nodes of every manifest in `manifest_dir`, plus schema errors."""
    nodes: dict[str, Node] = {}
    errors: list[str] = []
    for f in sorted(Path(manifest_dir).glob("*.yaml")):
        doc = yaml.safe_load(f.read_text()) or {}
        pipeline = doc.get("pipeline", f.stem)
        if set(doc) - {"pipeline", "code_ref", "nodes"}:
            errors.append(
                f"{f.name}: claves de nivel superior desconocidas {sorted(set(doc) - {'pipeline', 'code_ref', 'nodes'})}"
            )
        for nid, spec in (doc.get("nodes") or {}).items():
            errs = _schema_errors(nid, spec)
            if nid in nodes:
                errs.append(f"{nid}: id repetido ({f.name} y {nodes[nid].pipeline})")
            errors += [f"{f.name}: {e}" for e in errs]
            if errs:
                continue
            nodes[nid] = Node(
                id=nid,
                pipeline=pipeline,
                estado=spec["estado"],
                code_ref=spec.get("code_ref", doc.get("code_ref")),
                code_paths=spec.get("code_paths", []),
                inputs=spec.get("inputs", []),
                paths=spec.get("paths", []),
                fingerprint=spec.get("fingerprint", {}),
                checks=spec.get("checks", []),
                observer=spec.get("observer"),
                raw=spec,
            )
    return nodes, errors


def topo_order(nodes: dict[str, Node]) -> tuple[list[str], list[str]]:
    """Inputs before consumers; the second list names each cycle found."""
    order, cycles, state = [], [], {}

    def visit(nid: str, stack: list[str]) -> None:
        if state.get(nid) == "done":
            return
        if state.get(nid) == "open":
            cycles.append(" -> ".join(stack[stack.index(nid) :] + [nid]))
            return
        state[nid] = "open"
        for dep in nodes[nid].inputs:
            if dep in nodes:
                visit(dep, stack + [nid])
        state[nid] = "done"
        order.append(nid)

    for nid in sorted(nodes):
        visit(nid, [])
    return order, cycles
