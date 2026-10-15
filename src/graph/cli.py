"""`po graph`: the asset manifests, read-only."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from graph.manifest import MANIFEST_DIR, MACHINES

_manifests_opt = click.option(
    "--manifests", "manifest_dir", type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=MANIFEST_DIR, show_default=True, help="Directory of manifest YAMLs.",
)


@click.group()
def graph():
    """Asset graph: manifests, validation, code fingerprints."""


@graph.command("validate")
@_manifests_opt
@click.option("--rev", default=None, help="Check every code_path at this git rev instead of each node's code_ref.")
@click.option("--machine", type=click.Choice(MACHINES), default=None,
              help="Also glob each data path declared on this machine for >= 1 hit.")
def validate_cmd(manifest_dir, rev, machine):
    """DAG without cycles, inputs are nodes, code_paths exist."""
    from graph.validate import check_paths, validate

    nodes, errors, warnings = validate(manifest_dir, rev)
    if machine:
        for nid, g, hit in check_paths(nodes, machine):
            click.echo(f"  {'ok  ' if hit else 'NADA'} {nid}  {g}")
            if not hit:
                errors.append(f"{nid}: {g} no encuentra nada en {machine}")
    for w in warnings:
        click.echo(f"aviso: {w}")
    for e in errors:
        click.echo(f"error: {e}")
    by_pipeline = {}
    for node in nodes.values():
        by_pipeline[node.pipeline] = by_pipeline.get(node.pipeline, 0) + 1
    click.echo(f"{len(nodes)} nodos {by_pipeline}; {len(errors)} errores; {len(warnings)} avisos")
    sys.exit(1 if errors else 0)


@graph.command("fingerprint")
@_manifests_opt
@click.option("--node", "only", multiple=True, help="Print only these nodes (all are computed).")
@click.option("--json", "as_json", is_flag=True, help="Full detail as JSON.")
def fingerprint_cmd(manifest_dir, only, as_json):
    """Code fingerprint per node, folding in its inputs."""
    from graph.fingerprint import fingerprints
    from graph.manifest import load

    nodes, errors = load(manifest_dir)
    if errors:
        raise click.ClickException("; ".join(errors))
    fps = fingerprints(nodes)
    if only:
        fps = {k: v for k, v in fps.items() if k in only}
    if as_json:
        click.echo(json.dumps(fps, indent=2, sort_keys=True, default=str))
        return
    for nid in sorted(fps):
        d = fps[nid]
        notes = d["warnings"] + [f"sin archivos: {g}" for g in d["missing"]]
        click.echo(f"{d['fingerprint']}  {d['own']}  {nid:<24} files={d['n_files']}"
                   + (f"  [{'; '.join(notes)}]" if notes else ""))
