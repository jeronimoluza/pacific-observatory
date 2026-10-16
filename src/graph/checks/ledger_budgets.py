"""Ledger checks per source, from ``source_budgets.parquet`` (``po graph ledger budgets``).

- red: a new zero streak, >= 2 runs in a row with 0 rows after the source had rows;
- yellow: the last run took longer than the budget derived from the runs before it.

Findings go on ``prices.raw`` (partition ``<region>/<country>/<source>``, as its observer)
and ``text.delta`` (same shape), only when that node was observed in this status run.
"""

from __future__ import annotations

NODES = {"prices": "prices.raw", "text": "text.delta"}


def check(rows: list[dict]) -> list[dict]:
    from graph.ledger.store import BUDGETS, read

    seen = {r["node"] for r in rows}
    if not seen & set(NODES.values()):
        return []
    b = read(BUDGETS)
    if b is None:
        return []
    out = []
    for r in b.itertuples():
        node = NODES.get(r.pipeline)
        if node not in seen:
            continue
        part = f"{r.region}/{r.country}/{r.source}"
        if r.new_zero_streak:
            out.append({"node": node, "partition": part, "color": "rojo",
                        "msg": f"racha nueva de ceros: {r.zero_streak} corridas con 0 filas"})
        if r.over_budget:
            out.append({"node": node, "partition": part, "color": "amarillo",
                        "msg": f"duración {r.last_duration_s:.0f}s > presupuesto {r.budget_prev_s:.0f}s"})
    return out
