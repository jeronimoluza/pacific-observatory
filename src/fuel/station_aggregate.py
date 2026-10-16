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
``max_dispersion``. The raw keeps every station (``station`` column, else
address/city/subnational area); the build aggregates and writes the stats to
``station_stats.csv`` in the country's outputs, and publish turns flagged
periods yellow.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pandas as pd
import yaml
from pydantic import BaseModel, ConfigDict

STATS_FILE = "station_stats.csv"


class StationAggregate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stat: Literal["median", "mean"] = "median"
    trim: Literal["mad", "none"] = "mad"
    k: float = 3.0
    min_stations: int = 5
    max_dispersion: float = 0.25
    # Location labels that are aggregates themselves (RTEP's "national_avg").
    exclude: list[str] = []


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
        price_mean, price_median = prices.mean(), keep.median()
        q1, q3 = keep.quantile([0.25, 0.75])
        dispersion = (q3 - q1) / price if price else float("nan")
        n = len(keep)
        rows.append(
            {
                **dict(zip(keys, key if isinstance(key, tuple) else (key,))),
                "price": round(float(price), 4),
                "price_mean": round(float(price_mean), 4),
                "price_median": round(float(price_median), 4),
                "price_trimmed_mean": round(float(keep.mean()), 4),
                "n_stations": n,
                "n_dropped": len(prices) - n,
                "dispersion": round(float(dispersion), 4),
                "flagged": bool(
                    n < cfg.min_stations or dispersion > cfg.max_dispersion
                ),
            }
        )
    return pd.DataFrame(rows)


NATIONAL = "national"
_INFERRED_TYPE = {
    "station": "station",
    "address": "station",
    "city": "city",
    "subnational_area": "region",
}


def _present(s: pd.Series) -> pd.Series:
    return s.notna() & s.astype(str).str.strip().ne("") & s.astype(str).ne("nan")


def fill_station(df: pd.DataFrame, station_type: str | None = None) -> pd.DataFrame:
    """Give every row ``station`` and ``station_type``.

    station: the row's own value, else address, city, subnational area, else
    "national". station_type: the row's own value, else the source's
    ``station_type`` (YAML) for rows with a location, else inferred from the
    column the station came from.
    """
    out = df.copy()
    station = pd.Series(NATIONAL, index=out.index, dtype="object")
    stype = pd.Series(NATIONAL, index=out.index, dtype="object")
    for col in ("subnational_area", "city", "address", "station"):
        if col in out.columns:
            has = _present(out[col])
            station = station.where(~has, out[col].astype(str).str.strip())
            stype = stype.where(~has, _INFERRED_TYPE[col])
    if station_type:
        stype = stype.where(station.eq(NATIONAL), station_type)
    if "station_type" in out.columns:
        stype = out["station_type"].where(_present(out["station_type"]), stype)
    out["station"], out["station_type"] = station, stype
    return out


def hash_fields(row, base: list[str]) -> list[str]:
    """``base`` plus station only when it says something the other location
    fields don't, so rows stored before the station column keep their hash."""
    st = row.get("station")
    if st is None or (isinstance(st, float) and pd.isna(st)) or st in ("", NATIONAL):
        return base
    if any(
        str(row.get(c)).strip() == st for c in ("address", "city", "subnational_area")
    ):
        return base
    return base + ["station"]


def collapse_stations(
    df: pd.DataFrame, configs: dict[str, StationAggregate]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Replace the station-level rows of sources with ``station_aggregate`` by
    one robust row per (source, date, series); return (rows, station stats)."""
    keys = ["source_key", "observation_date", "series_key"]
    mask = df["source_key"].isin(list(configs))
    if not mask.any():
        return df, pd.DataFrame()
    rest, frames, stats = df[~mask], [], []
    for source_key, sub in df[mask].groupby("source_key"):
        sub = sub.assign(_station=fill_station(sub)["station"])
        sub = sub[~sub["_station"].isin(configs[source_key].exclude)]
        order = "scrape_ts" if "scrape_ts" in sub.columns else "observation_date"
        st = aggregate(sub, keys, "_station", "price_local", order, configs[source_key])
        meta = sub.drop_duplicates(keys).drop(columns=["price_local", "_station"])
        frames.append(
            meta.merge(st[[*keys, "price"]], on=keys).rename(
                columns={"price": "price_local"}
            )
        )
        stats.append(st)
    return (
        pd.concat([rest, *frames], ignore_index=True),
        pd.concat(stats, ignore_index=True),
    )


STATIONS_FILE = "stations.csv"
_TAGS_DIR = Path(__file__).resolve().parent / "configs" / "_stations"


def _tags() -> dict[tuple[str, str], str]:
    """{(source_key, station): "tag1;tag2"} from configs/_stations/*.yaml."""
    out: dict[tuple[str, str], str] = {}
    for path in sorted(_TAGS_DIR.glob("*.yaml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for source_key, stations in (doc.get("sources") or {}).items():
            for station, tags in (stations or {}).items():
                out[(source_key, str(station))] = ";".join(tags or [])
    return out


def station_outputs(
    combined: pd.DataFrame, entries: list[dict], out_dir: Path
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fill station/station_type per source, collapse sources with
    station_aggregate, write station_stats.csv and stations.csv to ``out_dir``.
    Returns (rows, station stats)."""
    by_key = {e["source_key"]: e for e in entries}
    combined = pd.concat(
        [
            fill_station(g, by_key.get(k, {}).get("station_type"))
            for k, g in combined.groupby("source_key", sort=False)
        ],
        ignore_index=True,
    )
    configs = {
        k: e["station_aggregate"]
        for k, e in by_key.items()
        if e.get("station_aggregate") is not None
    }
    collapsed, stats = collapse_stations(combined, configs)
    out_dir.mkdir(parents=True, exist_ok=True)
    if not stats.empty:
        stats.to_csv(out_dir / STATS_FILE, index=False, date_format="%Y-%m-%d")
    admin1 = combined["subnational_area"] if "subnational_area" in combined else None
    stations = (
        combined.assign(
            admin1=admin1.where(admin1.astype(str).ne(combined["station"]))
            if admin1 is not None
            else None
        )
        .groupby(["source_key", "station", "station_type"], as_index=False)
        .agg(
            admin1=("admin1", "first"),
            first_date=("observation_date", "min"),
            last_date=("observation_date", "max"),
            n_obs=("price_local", "size"),
        )
    )
    tags = _tags()
    stations["lat"] = None
    stations["lon"] = None
    stations["tags"] = [
        tags.get((k, s), "")
        for k, s in zip(stations["source_key"], stations["station"])
    ]
    stations.to_csv(out_dir / STATIONS_FILE, index=False, date_format="%Y-%m-%d")
    return collapsed, stats


STATION_COLUMNS = [
    "price_mean",
    "price_median",
    "n_stations",
    "n_dropped",
    "dispersion",
]


def attach_station_stats(df: pd.DataFrame, stats: pd.DataFrame) -> pd.DataFrame:
    """Add STATION_COLUMNS of the observation date a row
    comes from (``observed_on``) for station-aggregated sources; blank elsewhere."""
    if stats.empty:
        return df.assign(**{c: None for c in STATION_COLUMNS})
    keys = ["source_key", "observation_date", "series_key"]
    st = stats[[*keys, *STATION_COLUMNS]].copy()
    st["observation_date"] = pd.to_datetime(st["observation_date"])
    out = df.copy()
    out["_d"] = pd.to_datetime(out["observed_on"])
    out = out.merge(
        st.rename(columns={"observation_date": "_d"}),
        on=["source_key", "_d", "series_key"],
        how="left",
    )
    return out.drop(columns="_d")
