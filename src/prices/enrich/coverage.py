"""Production coverage of the COICOP classifier. `prices coverage`.

Answers the question gold cross-validation cannot: of the products actually in
the corpus, how many resolve to a COICOP leaf — per country, and which leaves
are missing where.

This is deliberately NOT the gold metric. On gold, `coverage = correct AND
accepted / all rows` against a known label. Here there is no ground truth, so
coverage is `resolved / all products`, and precision is inherited from the
operating point (tau was fitted at the 98% floor on gold, not re-measured here).
The two numbers are not comparable, and a gap between them is expected: gold is
a stratified sample drawn from low-density parts of the space, not a sample of
the corpus.

Five row states are reported side by side and never merged, because they imply
different remedies:

  classified    the gate cleared tau and no veto fired
  narrow_source the source declared a narrow COICOP; bypassed the classifier
  flagged_basis a leaf WAS assigned, then demoted by the basis audit
  rejected      the classifier looked and would not commit  -> a model problem
  unembedded    no vector in the store, never scored        -> a backlog problem

Collapsing `unembedded` into `rejected` would make the headline actively
misleading, since the first is a scraping/embedding gap and the second is model
coverage.

Every rate is reported BOTH unique-product-weighted and observation-weighted
(`n_rows`). The team has not adopted a convention, so this module refuses to
pick one on their behalf.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import click
import pandas as pd

from prices.enrich import config

RESOLVED_STATES = ("classified", "narrow_source")
ALL_STATES = (
    "classified",
    "narrow_source",
    "flagged_basis",
    "rejected",
    "unembedded",
)

REPORT_ROOT = config.REPO_ROOT / "outputs" / "prices" / "coverage"

_DECISION_COLS = ["input_hash", "coicop_code", "state", "leaf_top1", "gate_score"]
_PRODUCT_COLS = ["input_hash", "country", "region", "source", "n_rows"]


def load_joined(
    decisions_path: Optional[Path] = None,
    products_path: Optional[Path] = None,
) -> pd.DataFrame:
    """Decisions joined to their product metadata, one row per input_hash.

    Only the columns the report needs are read — the full decision table carries
    the structural extraction fields too, and the corpus is large enough that
    projecting matters.
    """
    decisions_path = decisions_path or config.DECISIONS_PARQUET
    products_path = products_path or config.PRODUCTS_INPUT_PARQUET
    dec = pd.read_parquet(decisions_path, columns=_DECISION_COLS)
    prod = pd.read_parquet(products_path, columns=_PRODUCT_COLS)
    df = dec.merge(prod, on="input_hash", how="left", validate="one_to_one")
    df["country"] = df["country"].fillna("").astype(str)
    df["source"] = df["source"].fillna("").astype(str)
    df["region"] = df["region"].fillna("").astype(str)
    df["n_rows"] = df["n_rows"].fillna(1).astype("int64")
    df["state"] = df["state"].fillna("rejected").astype(str)
    df["resolved"] = df["state"].isin(RESOLVED_STATES)
    return df


def _rates(df: pd.DataFrame, keys: list[str] | None) -> pd.DataFrame:
    """Product- and observation-weighted totals plus resolved counts/rates."""
    work = df.copy()
    work["obs_resolved"] = work["n_rows"].where(work["resolved"], 0)
    if keys:
        g = work.groupby(keys, dropna=False)
    else:
        work["_all"] = ""
        g = work.groupby("_all", dropna=False)
    out = g.agg(
        n_products=("input_hash", "size"),
        n_products_resolved=("resolved", "sum"),
        n_observations=("n_rows", "sum"),
        n_observations_resolved=("obs_resolved", "sum"),
    ).reset_index()
    if not keys:
        out = out.drop(columns=["_all"])
    out["n_products_resolved"] = out["n_products_resolved"].astype("int64")
    out["coverage_products"] = out["n_products_resolved"] / out["n_products"]
    out["coverage_observations"] = (
        out["n_observations_resolved"] / out["n_observations"].replace(0, pd.NA)
    ).astype(float)
    return out


def _state_counts(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """One column per row state, product- and observation-weighted."""
    prod = (
        df.pivot_table(
            index=keys,
            columns="state",
            values="input_hash",
            aggfunc="size",
            fill_value=0,
            observed=False,
        )
        .reindex(columns=list(ALL_STATES), fill_value=0)
        .add_prefix("n_products_")
    )
    obs = (
        df.pivot_table(
            index=keys,
            columns="state",
            values="n_rows",
            aggfunc="sum",
            fill_value=0,
            observed=False,
        )
        .reindex(columns=list(ALL_STATES), fill_value=0)
        .add_prefix("n_observations_")
    )
    return prod.join(obs).reset_index()


def leaf_universe(df: pd.DataFrame) -> list[str]:
    """Every COICOP leaf this corpus can produce.

    The union of leaves actually assigned and leaves the head named as top-1
    anywhere. Derived from the data rather than the taxonomy file on purpose:
    the actionable question is "which leaves does this country lack that others
    have", not "which leaves exist in COICOP 2018".
    """
    assigned = df.loc[df["resolved"], "coicop_code"].dropna().astype(str)
    top1 = df["leaf_top1"].dropna().astype(str)
    return sorted(set(assigned) | set(top1))


def country_leaf_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """country x leaf, with accepted volume AND top-1 volume.

    Carrying `n_products_top1` next to `n_products_accepted` is what makes the
    answer actionable: it separates "this country has no such product" from
    "it has them, but the gate would not commit to them". Those have completely
    different fixes — go scrape, versus go label.
    """
    acc = (
        df[df["resolved"] & df["coicop_code"].notna()]
        .groupby(["country", "coicop_code"], dropna=False)
        .agg(
            n_products_accepted=("input_hash", "size"),
            n_observations_accepted=("n_rows", "sum"),
        )
        .reset_index()
        .rename(columns={"coicop_code": "leaf"})
    )
    top = (
        df[df["leaf_top1"].notna()]
        .groupby(["country", "leaf_top1"], dropna=False)
        .agg(
            n_products_top1=("input_hash", "size"),
            n_observations_top1=("n_rows", "sum"),
        )
        .reset_index()
        .rename(columns={"leaf_top1": "leaf"})
    )
    out = acc.merge(top, on=["country", "leaf"], how="outer")
    for c in (
        "n_products_accepted",
        "n_observations_accepted",
        "n_products_top1",
        "n_observations_top1",
    ):
        out[c] = out[c].fillna(0).astype("int64")
    return out.sort_values(["country", "leaf"]).reset_index(drop=True)


def missing_leaves(df: pd.DataFrame, matrix: pd.DataFrame) -> pd.DataFrame:
    """Leaves absent per country — the literal answer to "can I find eggs in Japan".

    Two flavours per (country, leaf): `missing_accepted` is true when nothing was
    trusted into that leaf, `missing_entirely` when the head never even named it.
    A leaf that is missing_accepted but NOT missing_entirely is a labeling
    target; one that is missing_entirely is a sourcing target.
    """
    leaves = leaf_universe(df)
    countries = sorted(c for c in df["country"].unique() if c)
    full = pd.MultiIndex.from_product(
        [countries, leaves], names=["country", "leaf"]
    ).to_frame(index=False)
    out = full.merge(matrix, on=["country", "leaf"], how="left")
    for c in (
        "n_products_accepted",
        "n_observations_accepted",
        "n_products_top1",
        "n_observations_top1",
    ):
        out[c] = out[c].fillna(0).astype("int64")
    out["missing_accepted"] = out["n_products_accepted"] == 0
    out["missing_entirely"] = (out["n_products_accepted"] == 0) & (
        out["n_products_top1"] == 0
    )
    return out


def build_report(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    matrix = country_leaf_matrix(df)
    df = df.copy()
    df["division"] = df["coicop_code"].astype("string").str.slice(0, 2)
    df["division_top1"] = df["leaf_top1"].astype("string").str.slice(0, 2)
    return {
        "coverage_overall": _rates(df, None),
        "coverage_by_country": _rates(df, ["country"]).sort_values(
            "n_products", ascending=False
        ),
        "coverage_by_region": _rates(df, ["region"]),
        "coverage_by_source": _rates(df, ["country", "source"]).sort_values(
            "n_products", ascending=False
        ),
        "coverage_by_country_division": _rates(
            df[df["resolved"]], ["country", "division"]
        ),
        "coverage_by_division_top1": _rates(df, ["division_top1"]),
        "state_breakdown_by_country": _state_counts(df, ["country"]),
        "state_breakdown_overall": _state_counts(df.assign(_k=""), ["_k"]).drop(
            columns=["_k"]
        ),
        "country_leaf_matrix": matrix,
        "leaves_missing_by_country": missing_leaves(df, matrix),
    }


def _summary_text(df: pd.DataFrame, rep: dict[str, pd.DataFrame]) -> str:
    o = rep["coverage_overall"].iloc[0]
    lines = [
        "",
        f"PRODUCTION COVERAGE  —  {int(o['n_products']):,} products, "
        f"{int(o['n_observations']):,} observations, "
        f"{df['country'].nunique()} countries",
        "",
        "  resolved (classified + narrow_source)",
        f"    by unique product : {o['coverage_products']:.1%}  "
        f"({int(o['n_products_resolved']):,})",
        f"    by observation    : {o['coverage_observations']:.1%}  "
        f"({int(o['n_observations_resolved']):,})",
        "",
        "  row states (unique products):",
    ]
    st = rep["state_breakdown_overall"].iloc[0]
    total = int(o["n_products"])
    for s in ALL_STATES:
        n = int(st.get(f"n_products_{s}", 0))
        lines.append(f"    {s:<14} {n:>12,}  {n / total:6.1%}")

    by_c = rep["coverage_by_country"]
    big = by_c[by_c["n_products"] >= 1000].sort_values("coverage_products")
    lines += ["", "  weakest countries (>=1000 products):"]
    for _, r in big.head(10).iterrows():
        lines.append(
            f"    {r['country'][:28]:<28} {r['coverage_products']:6.1%}  "
            f"({int(r['n_products']):,} products)"
        )
    lines += ["", "  strongest countries (>=1000 products):"]
    for _, r in big.tail(10).iloc[::-1].iterrows():
        lines.append(
            f"    {r['country'][:28]:<28} {r['coverage_products']:6.1%}  "
            f"({int(r['n_products']):,} products)"
        )

    miss = rep["leaves_missing_by_country"]
    lines += [
        "",
        f"  leaf gaps: {int(miss['missing_accepted'].sum()):,} of {len(miss):,} "
        f"(country, leaf) cells have nothing accepted; "
        f"{int(miss['missing_entirely'].sum()):,} were never even predicted",
        "",
    ]
    return "\n".join(lines)


def run(
    decisions_path: Optional[Path] = None,
    products_path: Optional[Path] = None,
    out_root: Optional[Path] = None,
    verbose: bool = True,
) -> dict:
    out_root = Path(out_root) if out_root else REPORT_ROOT
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = out_root / stamp
    out_dir.mkdir(parents=True, exist_ok=True)

    if verbose:
        print("loading decisions + products ...", flush=True)
    df = load_joined(decisions_path, products_path)
    if verbose:
        print(f"  {len(df):,} products joined", flush=True)

    rep = build_report(df)
    for name, frame in rep.items():
        frame.to_parquet(out_dir / f"{name}.parquet", index=False)

    o = rep["coverage_overall"].iloc[0]
    manifest = {
        "generated_utc": stamp,
        "decisions_path": str(decisions_path or config.DECISIONS_PARQUET),
        "products_path": str(products_path or config.PRODUCTS_INPUT_PARQUET),
        "n_products": int(o["n_products"]),
        "n_observations": int(o["n_observations"]),
        "n_countries": int(df["country"].nunique()),
        "n_sources": int(df["source"].nunique()),
        "coverage_products": float(o["coverage_products"]),
        "coverage_observations": float(o["coverage_observations"]),
        "resolved_states": list(RESOLVED_STATES),
        "note": (
            "Coverage here is resolved/all products on the real corpus. It is NOT "
            "the gold coverage@98 metric and is not comparable to it: gold is a "
            "stratified sample and carries ground truth, this does not. No "
            "product-vs-observation weighting convention has been adopted, so "
            "both are reported."
        ),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    latest = out_root / "latest"
    if latest.is_symlink() or latest.exists():
        latest.unlink()
    latest.symlink_to(out_dir.name)

    if verbose:
        print(_summary_text(df, rep))
        print(f"  wrote {len(rep)} tables to {out_dir}")
    return manifest


@click.command(name="coverage")
@click.option(
    "--out-root",
    default=None,
    type=click.Path(file_okay=False),
    help=f"Report root (default {REPORT_ROOT}).",
)
@click.option(
    "--decisions",
    default=None,
    type=click.Path(dir_okay=False),
    help="Decision table (default the classify stage's decisions.parquet).",
)
def coverage_command(out_root, decisions):
    """Production COICOP coverage: how much of the real corpus resolves, by country.

    Read-only. Reads the classify stage's full decision table (which retains
    rejects) and reports resolved-vs-total per country, per division and per
    leaf, both unique-product- and observation-weighted.
    """
    run(decisions_path=Path(decisions) if decisions else None, out_root=out_root)
