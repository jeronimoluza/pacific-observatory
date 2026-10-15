"""Registered checks, run by `graph status` over every observer row.

A check is `check(rows: list[dict]) -> list[dict]`: it reads observer rows (keys in
`graph.observe.ROW_KEYS`) and returns one finding per failing partition,
`{"node", "partition", "color", "msg"}`, color "rojo" or "amarillo" (absent = verde).
Partition "*" colors the whole node. Checks only read; they never fix.
"""

CHECKS: list = []
