"""Where rows and product names stop, per country: raw files to Stage B.

A report, not a stage: it reads what each stage already wrote and changes
none of them. Rows are dated observation rows at every step; names are
distinct product names (hashed). Steps, in order:

- raw: every non-empty line of a source's raw files (a CC json file is one
  line, a fetcher CSV row is one line)
- concatenate: lines that do not parse, out-of-stock rows, and rows screened
  for a missing required field. The last is rows read minus rows in the
  shard, so a shard older than its raw files shows up here too.
- prepare: rows that reach products_input. prepare collapses rows into
  products and filters nothing, so a loss here is unexplained.
- classify: each product's decision state. 01 + 02.1 after the COICOP
  overrides (Stage B's own `load_products`) goes to Stage B.
- stage_b: each dated row's `stage_b_status`.

Writes outputs/prices/drop_ledger/<country>.parquet, one row per
(source, step, outcome), and prints the country table. Unparseable and
out-of-stock rows carry no name, so their `names` is empty.
"""

from __future__ import annotations

from collections import Counter

import click
import numpy as np
import pandas as pd
import pyarrow.dataset as pads
import pyarrow.parquet as pq

from prices import partition
from prices.enrich import config
from prices.enrich.stages import decisions_store
from prices.enrich.stages.concatenate import (
    DATA_PRICES_ROOT, PER_SOURCE_DIR, _iter_rows, _iter_source_files, _walk_sources,
)
from prices.stage_b import OUT_ROOT as STAGE_B_ROOT, load_products

OUT_DIR = config.REPO_ROOT / "outputs" / "prices" / "drop_ledger"
_CHUNK = 1_000_000


def _hash(names) -> np.ndarray:
    return pd.util.hash_array(pd.Series(names, dtype=object).fillna("").astype(str).to_numpy())


def _lines(shape: str, path) -> int:
    if shape == "cc":
        return 1
    with path.open("rb") as fh:
        n = sum(1 for line in fh if line.strip())
    return n - 1 if shape == "price_obs" else n


def _raw(country: str) -> tuple[list[dict], dict[str, np.ndarray]]:
    """Per source: lines, rows read, out-of-stock; and the hashed names read."""
    counts, names = [], {}
    for *_, c, source, source_dir in _walk_sources(DATA_PRICES_ROOT):
        if c != country:
            continue
        files = _iter_source_files(source_dir, c, source)
        if not files:
            continue
        stats: Counter = Counter()
        read, chunks, buf = 0, [], []
        for row in _iter_rows(files, stats):
            buf.append(row.get("product_name"))
            if len(buf) == _CHUNK:
                chunks.append(np.unique(_hash(buf)))
                read, buf = read + len(buf), []
        read += len(buf)
        chunks.append(_hash(buf))
        names[source] = np.unique(np.concatenate(chunks))
        counts.append({"source": source, "lines": sum(_lines(s, p) for s, p in files),
                       "read": read, "out_of_stock": stats["out_of_stock"]})
    return counts, names


def _shards(country: str) -> pd.DataFrame:
    selector = partition.selector_from_flags(None, None, country)
    frames = [
        pq.read_table(s.path, columns=["source", "product_name"]).to_pandas()
        .assign(name=lambda d: _hash(d.pop("product_name")))
        .groupby(["source", "name"]).size().rename("rows").reset_index()
        for s in partition.select([selector], PER_SOURCE_DIR)
    ]
    return pd.concat(frames, ignore_index=True)


def ledger(country: str) -> pd.DataFrame:
    """Long table: source, step, outcome, rows, and the hashed names behind it."""
    parts = []

    def add(step, outcome, df):
        parts.append(df.assign(step=step, outcome=outcome)[["source", "step", "outcome", "name", "rows"]])

    counts, raw_names = _raw(country)
    shard = _shards(country)
    for c in counts:
        s, names = c["source"], raw_names[c["source"]]
        kept = shard[shard["source"].eq(s)]
        one = lambda n: pd.DataFrame({"source": [s], "name": [None], "rows": [n]})
        add("raw", "lines", pd.DataFrame({"source": s, "name": names, "rows": 0}))
        add("raw", "lines", one(c["lines"]))
        add("concatenate", "unparseable", one(c["lines"] - c["read"] - c["out_of_stock"]))
        add("concatenate", "out_of_stock", one(c["out_of_stock"]))
        lost = np.setdiff1d(names, kept["name"].unique())
        add("concatenate", "missing_field", pd.DataFrame({"source": s, "name": lost, "rows": 0}))
        add("concatenate", "missing_field", one(c["read"] - kept["rows"].sum()))
    add("concatenate", "kept", shard)

    prod = (
        pads.dataset(config.PRODUCTS_INPUT_PARQUET)
        .to_table(columns=["input_hash", "product_name_original", "source", "n_rows"],
                  filter=pads.field("country") == country)
        .to_pandas()
    )
    prod["name"] = _hash(prod["product_name_original"])
    prod = prod.rename(columns={"n_rows": "rows"})
    gap = shard.groupby("source")["rows"].sum().sub(prod.groupby("source")["rows"].sum(), fill_value=0)
    add("prepare", "lost", gap.rename("rows").reset_index().assign(name=None))
    add("prepare", "kept", prod)

    part = decisions_store.parts_root(config.CLASSIFIED_HIERLEX_PARQUET) / (
        decisions_store.part_name(country) + ".parquet"
    )
    state = pd.read_parquet(part, columns=["input_hash", "state"]).drop_duplicates("input_hash")
    state = prod["input_hash"].map(state.set_index("input_hash")["state"]).fillna("no decision")
    state = state.replace("classified", "non-food")
    state[prod["input_hash"].isin(set(load_products(country)["input_hash"]))] = "to Stage B"
    for outcome, df in prod.groupby(state):
        add("classify", outcome, df)

    ob = pd.read_parquet(
        STAGE_B_ROOT / decisions_store.part_name(country) / "observations.parquet",
        columns=["input_hash", "source", "stage_b_status"],
    )
    ob["name"] = ob["input_hash"].map(prod.set_index("input_hash")["name"])
    for outcome, df in ob.assign(rows=1).groupby("stage_b_status"):
        add("stage_b", outcome, df)
    return pd.concat(parts, ignore_index=True)


def summarise(long: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    order = {s: i for i, s in enumerate(["raw", "concatenate", "prepare", "classify", "stage_b"])}
    out = long.groupby(by + ["step", "outcome"], sort=False).agg(
        rows=("rows", "sum"), names=("name", "nunique")
    ).reset_index()
    return out.sort_values(by + ["step"], key=lambda s: s.map(order) if s.name == "step" else s,
                           kind="stable", ignore_index=True)


@click.command("drop-ledger")
@click.option("--country", "countries", required=True, multiple=True, help="Country slug; repeatable.")
def drop_ledger(countries: tuple[str, ...]) -> None:
    """Rows and distinct product names lost at each step, raw files to Stage B."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for country in countries:
        long = ledger(country)
        summarise(long, ["source"]).to_parquet(OUT_DIR / f"{country}.parquet", index=False)
        click.echo(f"\n{country}\n{summarise(long, []).to_string(index=False)}")
