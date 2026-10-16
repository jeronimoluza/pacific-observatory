"""`graph status`: every node's observer rows, the registered checks' colors, and
the drift each observer reports (reported, never fixed)."""

from __future__ import annotations

from graph.checks import CHECKS
from graph.manifest import Node, topo_order
from graph.observe import observe

RANK = {"verde": 0, "amarillo": 1, "rojo": 2}


def collect(nodes: dict[str, Node], only: tuple[str, ...] = ()) -> list[dict]:
    order, _ = topo_order(nodes)
    rows = []
    for nid in order:
        if nodes[nid].observer and (not only or nid in only):
            rows += observe(nodes[nid])
    return rows


def country_of(partition: str, countries: set[str]) -> str | None:
    return next((p for p in partition.split("/") if p in countries), None)


def keep_countries(
    rows: list[dict], wanted: list[str], countries: set[str]
) -> list[dict]:
    """Rows of the wanted countries, plus rows that belong to no country (global)."""
    wanted = set(wanted)
    return [
        r
        for r in rows
        if (c := country_of(r["partition"], countries)) is None or c in wanted
    ]


def run_checks(rows: list[dict]) -> list[dict]:
    findings = []
    for check in CHECKS:
        findings += check(rows)
    return findings


def color_of(findings: list[dict]) -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    for f in findings:
        k = (f["node"], f["partition"])
        if RANK[f["color"]] > RANK.get(out.get(k, "verde"), 0):
            out[k] = f["color"]
    return out


def summary(rows: list[dict], findings: list[dict]) -> list[dict]:
    colors = color_of(findings)
    by_node: dict[str, dict] = {}
    for r in rows:
        s = by_node.setdefault(
            r["node"],
            {
                "node": r["node"],
                "partitions": 0,
                "done": 0,
                "rows": 0,
                "freshness_utc": None,
                "sha": set(),
                "drift": 0,
                "rojo": 0,
                "amarillo": 0,
            },
        )
        s["partitions"] += 1
        s["done"] += bool(r["done"])
        s["rows"] += r["rows"] or 0
        f = r["freshness_utc"]
        if f and (s["freshness_utc"] is None or f > s["freshness_utc"]):
            s["freshness_utc"] = f
        if r["sha"]:
            s["sha"].add(r["sha"][:8])
        s["drift"] += bool(r["drift"])
        c = colors.get((r["node"], r["partition"]))
        if c:
            s[c] += 1
    for f in findings:
        if f["partition"] == "*" and f["node"] in by_node:
            by_node[f["node"]][f["color"]] += 1
    for s in by_node.values():
        s["sha"] = ",".join(sorted(s["sha"])) or "-"
        s["color"] = "rojo" if s["rojo"] else "amarillo" if s["amarillo"] else "verde"
    return list(by_node.values())


def matrix(
    rows: list[dict], countries: list[str], all_countries: set[str]
) -> tuple[list[str], dict]:
    """country -> node -> [done, partitions, rows], for the given countries."""
    nodes = list(dict.fromkeys(r["node"] for r in rows))
    out = {c: {} for c in countries}
    for r in rows:
        c = country_of(r["partition"], all_countries)
        if c in out:
            cell = out[c].setdefault(r["node"], [0, 0, 0])
            cell[0] += bool(r["done"])
            cell[1] += 1
            cell[2] += r["rows"] or 0
    return [n for n in nodes if any(n in v for v in out.values())], out


def human(n: int) -> str:
    for div, suf in ((1e9, "G"), (1e6, "M"), (1e3, "k")):
        if n >= div:
            return f"{n / div:.1f}{suf}"
    return str(n)


def render_summary(summ: list[dict]) -> str:
    head = f"{'node':<22} {'done/parts':>11} {'rows':>14} {'freshness_utc':<26} {'sha':<18} {'drift':>5}  color"
    lines = [head, "-" * len(head)]
    for s in summ:
        lines.append(
            f"{s['node']:<22} {s['done']:>5}/{s['partitions']:<5} {s['rows']:>14,} "
            f"{s['freshness_utc'] or '-':<26} {s['sha'][:18]:<18} {s['drift']:>5}  {s['color']}"
            + (
                f" ({s['rojo']} rojo, {s['amarillo']} amarillo)"
                if s["color"] != "verde"
                else ""
            )
        )
    return "\n".join(lines)


def render_matrix(nodes: list[str], mat: dict) -> str:
    short = [n.removeprefix("prices.")[:13] for n in nodes]
    lines = [f"{'country':<26}" + "".join(f"{s:>14}" for s in short)]
    for c, cells in mat.items():
        line = f"{c:<26}"
        for n in nodes:
            d, p, rows = cells.get(n, [0, 0, 0])
            line += f"{(f'{d}/{p} {human(rows)}' if p else '-'):>14}"
        lines.append(line)
    return "\n".join(lines)
