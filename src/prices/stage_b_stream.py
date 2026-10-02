"""Stage B for one country, one group of COICOP leaves at a time.

Every step of `stage_b.run` stays inside a leaf: the band's cell (leaf x
country x unit), the imputation pool (country x leaf), the piece and per-kg
checks (leaf x source), an official product's own history and the dated-row
join (product). Only the local currency and the month FX rates are
country-wide; they are fixed once here and passed to every chunk. Peak memory
is then set by the largest chunk, not the country (Japan in one block passed
26 GB and was OOM-killed on a8, 2026-10-02).

The files hold the same rows as `stage_b.write`, grouped by chunk instead of
in `run`'s order, so the hand-check samples (drawn by position) differ.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import click
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from prices import stage_b as sb
from prices.enrich.stages import decisions_store
from prices.fx import attach as fx

# Products per chunk. A leaf is never split; one larger than this runs alone.
CHUNK_PRODUCTS = 100_000

_REPORT_OBS = ["input_hash", "trusted", "qa_level", "size_source", "stage_b_status", "coicop_code"]
_REPORT_PM = ["input_hash", "pricing_basis", "coicop_code", "basis_ok", "size_source", "unit_value_local", "source"]


def plan_chunks(codes: pd.Series, limit: int | None = None) -> list[list[str]]:
    """Leaves packed in order of size into chunks of at most `limit` products."""
    limit = limit or CHUNK_PRODUCTS
    chunks, cur, n = [], [], 0
    for leaf, k in codes.value_counts().items():
        if cur and n + k > limit:
            chunks.append(cur)
            cur, n = [], 0
        cur.append(leaf)
        n += k
    return chunks + [cur] if cur else chunks


def _concat(parts: list[Path], dest: Path, trusted_only: bool = False) -> int:
    """Append chunk files into `dest` one at a time; returns rows written.
    A column that is all null in one chunk is typed by the others."""
    schema = pa.unify_schemas([pq.read_schema(p) for p in parts], promote_options="permissive")
    schema = schema.remove_metadata()
    n = 0
    with pq.ParquetWriter(dest, schema) as w:
        for p in parts:
            t = pq.read_table(p).select(schema.names).cast(schema)
            if trusted_only:
                t = t.filter(pc.field("trusted"))
            w.write_table(t)
            n += t.num_rows
    return n


def run_and_write(country: str) -> tuple[int, int]:
    """Stage B for `country` chunk by chunk into `stage_b.OUT_ROOT`; (rows, trusted)."""
    products = sb.load_products(country)
    local = products["currency"].mode().iloc[0]
    months = sb.load_months(country, products["input_hash"])
    rates = sb.month_rates(months.assign(currency=months["currency"].map(fx.normalize_currency_safe)), local)
    del months
    root = sb.OUT_ROOT / decisions_store.part_name(country)
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        chunks = plan_chunks(products["coicop_code"])
        for i, leaves in enumerate(chunks):
            part = products[products["coicop_code"].isin(leaves)].reset_index(drop=True)
            out, pm = sb.run(country, part, local, rates)
            out.to_parquet(tmp / f"obs_{i:04d}.parquet", index=False)
            pm.to_parquet(tmp / f"pm_{i:04d}.parquet", index=False)
            print(f"  chunk {i + 1}/{len(chunks)}: {len(leaves)} leaves, {len(part):,} products, {len(out):,} rows", flush=True)
            del out, pm, part
        del products
        obs, pms = sorted(tmp.glob("obs_*.parquet")), sorted(tmp.glob("pm_*.parquet"))
        rows = _concat(obs, root / "observations.parquet")
        trusted = _concat(obs, root / "trusted_observations.parquet", trusted_only=True)
        _concat(pms, root / "product_months.parquet")
    out = pd.read_parquet(root / "observations.parquet", columns=list(dict.fromkeys(_REPORT_OBS + ["source"] + sb._SAMPLE_COLS)))
    pm = pd.read_parquet(root / "product_months.parquet", columns=_REPORT_PM)
    sb.write_checks(root, out, pm)
    return rows, trusted


@click.command("stage-b-streamed")
@click.argument("countries", nargs=-1, required=True)
def stage_b_streamed(countries: tuple[str, ...]) -> None:
    """Stage B per country, streamed by COICOP leaf."""
    for country in countries:
        rows, trusted = run_and_write(country)
        click.echo(f"DONE {country} rows={rows} trusted={trusted}")


if __name__ == "__main__":
    sys.exit(stage_b_streamed())
