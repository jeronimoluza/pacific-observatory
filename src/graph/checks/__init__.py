"""Registered checks, run by `graph status` over every observer row.

A check is `check(rows: list[dict]) -> list[dict]`: it reads observer rows (keys in
`graph.observe.ROW_KEYS`) and returns one finding per failing partition,
`{"node", "partition", "color", "msg"}`, color "rojo" or "amarillo" (absent = verde).
Partition "*" colors the whole node. Checks only read; they never fix.
"""

CHECKS: list = []

from graph.checks import fuel_country, fuel_status, fx, ledger_budgets, pages, raw_sources, rtcal, text_counts, text_graph  # noqa: E402

CHECKS += [raw_sources.check, rtcal.check, pages.check, fx.check, text_counts.check, text_graph.check,
           ledger_budgets.check, fuel_status.check, fuel_country.check]
