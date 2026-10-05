"""Canonical locations for the prices FX cache."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

#: Prices owns its own cache so the fuel and prices pipelines never contend
#: on one CSV.
PRICES_FX_CACHE = REPO_ROOT / "data" / "prices" / "_fx" / "fx_cache.csv"

#: The corpus's usable history starts here. This is a real floor now: it is
#: the start of the price corpus, not -- as the old 2024-03-06 value was --
#: whatever the shipped fetcher happened to reach.
FX_HISTORY_FLOOR = "2013-01-01"
