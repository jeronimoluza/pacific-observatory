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


@graph.command("status")
@_manifests_opt
@click.option("--week", default=None, help="ISO week, e.g. 2026-W42 (default: current, UTC). Fills <wk> and wNN.")
@click.option("--countries", default=None, help="Comma-separated slugs or a panel name (panel36).")
@click.option("--node", "only", multiple=True, help="Observe only these nodes.")
@click.option("--detail", is_flag=True, help="Also list every partition with drift or a check color.")
@click.option("--json", "as_json", is_flag=True, help="Rows, check findings and summary as JSON.")
def status_cmd(manifest_dir, week, countries, only, detail, as_json):
    """Observed state per node and partition: done, rows, freshness, SHA, drift, check colors."""
    import os

    from core.config import load_countries
    from graph.manifest import load
    from graph.status import (collect, color_of, keep_countries, matrix, render_matrix,
                              render_summary, run_checks, summary)
    from prices.weekly.panels import resolve_countries

    if week:
        os.environ["PO_GRAPH_WEEK"] = week
    from graph.observe import week as current

    nodes, errors = load(manifest_dir)
    if errors:
        raise click.ClickException("; ".join(errors))
    wanted = resolve_countries(countries)
    all_countries = set(load_countries())
    rows = collect(nodes, only)
    if wanted:
        rows = keep_countries(rows, wanted, all_countries)
    findings = run_checks(rows)
    summ = summary(rows, findings)
    if as_json:
        click.echo(json.dumps({"week": current(), "countries": wanted, "summary": summ,
                               "findings": findings, "rows": rows}, indent=1, default=str))
        return
    click.echo(f"week {current()}  countries {countries or 'all'}  checks {len(findings)} findings")
    click.echo(render_summary(summ))
    if wanted:
        click.echo("")
        click.echo(render_matrix(*matrix(rows, wanted, all_countries)))
    if detail:
        colors = color_of(findings)
        msgs = {}
        for f in findings:
            msgs.setdefault((f["node"], f["partition"]), []).append(f"{f['color']}: {f['msg']}")
        click.echo("")
        for r in rows:
            k = (r["node"], r["partition"])
            if r["drift"] or k in colors:
                click.echo(f"{r['node']:<22} {r['partition']:<50} {colors.get(k, 'verde'):<8} "
                           + "; ".join(r["drift"] + msgs.get(k, [])))


@graph.command("deadman")
@click.option("--expect", "expects", multiple=True, metavar="NAME@AT",
              help="Override deadman.expect.NAME.at, e.g. text-panel@daily-09:00 or prices-weekly@mon-09:30 (UTC).")
@click.option("--backup-mount", type=click.Path(path_type=Path), default=None,
              help="Default deadman.backup_mount of the notify config.")
def deadman_cmd(expects, backup_mount):
    """Rojo alert when an expected run has no fresh STATUS, the 5TB is not mounted or / is low."""
    from graph.deadman import run_deadman
    from notify.send import load_config

    overrides = {}
    for e in expects:
        name, sep, at = e.partition("@")
        if not sep:
            raise click.BadParameter(f"{e}: expected NAME@AT")
        overrides[name] = at
    sys.exit(run_deadman(load_config(), overrides, backup_mount, echo=click.echo))


from graph.ledger.cli import ledger  # noqa: E402

graph.add_command(ledger)
