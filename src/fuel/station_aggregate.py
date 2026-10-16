"""Robust station-to-national aggregation for sources that report per station.

Configured per source in YAML::

    station_aggregate: {stat: median, trim: mad, k: 3, min_stations: 5, max_dispersion: 0.25}

Per (product, period): each station first contributes one price (its last
report in the period, so a station that changes price ten times a month does
not count ten times); stations outside median ± k·scale are dropped, where
scale = max(1.4826·MAD, 2% of the median) so a market where most stations post
the same regulated price does not drop every station a cent away; the national
price is the median (or mean) of the rest. Per row it keeps n_stations,
n_dropped and dispersion = IQR / median of the kept stations, and flags
periods with fewer than ``min_stations`` or dispersion above
``max_dispersion``. The stats go to ``station_stats.csv`` next to the source's
``observations.csv``; publish turns flagged periods yellow.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict

STATS_FILE = "station_stats.csv"


class StationAggregate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stat: Literal["median", "mean"] = "median"
    trim: Literal["mad", "none"] = "mad"
    k: float = 3.0
    min_stations: int = 5
    max_dispersion: float = 0.25


def aggregate(
    df: pd.DataFrame,
    keys: list[str],
    station_col: str,
    price_col: str,
    order_col: str,
    cfg: StationAggregate,
) -> pd.DataFrame:
    """One row per ``keys`` with price, n_stations, n_dropped, dispersion, flagged."""
    per_station = (
        df.sort_values(order_col)
        .groupby([*keys, station_col], as_index=False)[price_col]
        .last()
    )
    rows = []
    for key, grp in per_station.groupby(keys):
        prices = grp[price_col].astype(float)
        med = prices.median()
        keep = prices
        if cfg.trim == "mad" and len(prices) >= 3:
            mad = (prices - med).abs().median()
            scale = max(1.4826 * mad, 0.02 * abs(med))
            keep = prices[(prices - med).abs() <= cfg.k * scale]
        price = keep.median() if cfg.stat == "median" else keep.mean()
        q1, q3 = keep.quantile([0.25, 0.75])
        dispersion = (q3 - q1) / price if price else float("nan")
        n = len(keep)
        rows.append(
            {
                **dict(zip(keys, key if isinstance(key, tuple) else (key,))),
                "price": round(float(price), 4),
                "n_stations": n,
                "n_dropped": len(prices) - n,
                "dispersion": round(float(dispersion), 4),
                "flagged": bool(
                    n < cfg.min_stations or dispersion > cfg.max_dispersion
                ),
            }
        )
    return pd.DataFrame(rows)


def write_stats(stats: pd.DataFrame, source_dir: Path, keys: list[str]) -> Path:
    """Upsert ``stats`` into ``source_dir/station_stats.csv``."""
    path = source_dir / STATS_FILE
    if path.exists():
        old = pd.read_csv(path, dtype={k: str for k in keys})
        stats = pd.concat(
            [old, stats.astype({k: str for k in keys})], ignore_index=True
        )
        stats = stats.drop_duplicates(subset=keys, keep="last")
    source_dir.mkdir(parents=True, exist_ok=True)
    stats.sort_values(keys).to_csv(path, index=False)
    return path
