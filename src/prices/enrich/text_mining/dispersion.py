"""F5 within-leaf unit-value dispersion (TMINE-06) — the dual-use output.

`build_f5` emits BOTH a human Markdown report AND the single stable machine
parquet (`f5_within_leaf_dispersion.parquet`) that downstream `build` re-reads
as a comparison-validity gate. High coefficient-of-variation (CoV) within a
single (COICOP leaf × country) cell flags a leaf that needs a sub-label split
(drives tier-b candidates) — that is the diagnostic. The same table, persisted
under the harness report dir, lets `build` suppress or flag non-comparable
cells — that is the gate.

This parquet is the ONE machine-artifact exception to the Markdown-only rule.
Its schema is LOCKED — `build` depends on the exact column set/order, so it must
not drift:

    coicop_leaf(str), country(str), n(int), unit_value_mean(float),
    unit_value_std(float), cov(float), dimension_mix(str json),
    n_suppressed_flag(bool)

Unit value per row:
- gold path: the canonical amount `val_gold` (the reliable diagnostic core);
  the dimension comes from `basis_gold`.
- corpus path: `price ÷ amount_value ÷ multiplier` where the spine
  (`split_spans`) resolved them (best-effort gate table); the dimension comes
  from the spine's `pricing_basis`.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from prices.enrich.text_mining import io
from prices.enrich.text_mining import report as md
from prices.enrich.text_mining.spine import split_spans

# Locked machine-table schema — column set AND order. Downstream `build`
# depends on this; do not reorder or rename.
F5_SCHEMA = [
    "coicop_leaf",
    "country",
    "n",
    "unit_value_mean",
    "unit_value_std",
    "cov",
    "dimension_mix",
    "n_suppressed_flag",
]

# The single machine artifact. Written under io.REPORT_DIR only.
F5_PARQUET_NAME = "f5_within_leaf_dispersion.parquet"
F5_MARKDOWN_NAME = "f5_within_leaf_dispersion.md"

# Cells with fewer than this many rows are flagged indicative-only.
LOW_N_FLOOR = 10


def _gold_rows(frame: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(
        {
            "coicop_leaf": frame["coicop_code_gold"].astype("string"),
            "country": frame["country"].astype("string"),
            "unit_value": pd.to_numeric(frame["val_gold"], errors="coerce"),
            "basis": frame["basis_gold"].astype("string"),
        }
    )
    return out.dropna(subset=["unit_value"])


def _corpus_rows(frame: pd.DataFrame) -> pd.DataFrame:
    leaves: list[str | None] = []
    countries: list[str | None] = []
    unit_values: list[float] = []
    bases: list[str | None] = []
    langs = frame["lang"] if "lang" in frame.columns else [None] * len(frame)
    leaf_col = (
        frame["declared_coicop_codes"]
        if "declared_coicop_codes" in frame.columns
        else [None] * len(frame)
    )
    for name, country, lang, price, leaf in zip(
        frame["product_name_original"],
        frame["country"],
        langs,
        frame["price"],
        leaf_col,
        strict=False,
    ):
        spans = split_spans(name if isinstance(name, str) else "", lang)
        amount = spans["amount_value"]
        multiplier = spans["multiplier"] or 1
        if price is None or amount in (None, 0) or multiplier == 0:
            continue
        try:
            uv = float(price) / float(amount) / float(multiplier)
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        if not np.isfinite(uv):
            continue
        leaves.append(leaf)
        countries.append(country)
        unit_values.append(uv)
        bases.append(spans["pricing_basis"])
    return pd.DataFrame(
        {
            "coicop_leaf": pd.Series(leaves, dtype="string"),
            "country": pd.Series(countries, dtype="string"),
            "unit_value": pd.Series(unit_values, dtype="float"),
            "basis": pd.Series(bases, dtype="string"),
        }
    ).dropna(subset=["unit_value"])


def _dimension_mix(bases: pd.Series) -> str:
    clean = bases.dropna()
    if clean.empty:
        return json.dumps({})
    shares = clean.value_counts(normalize=True)
    return json.dumps({str(k): float(v) for k, v in shares.items()}, sort_keys=True)


def _aggregate(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return pd.DataFrame(columns=F5_SCHEMA)

    records = []
    grouped = rows.groupby(["coicop_leaf", "country"], dropna=False, sort=True)
    for (leaf, country), group in grouped:
        values = group["unit_value"].to_numpy(dtype=float)
        n = int(len(values))
        mean = float(np.mean(values))
        # population std (ddof=0): a single-row group → 0.0, never NaN.
        std = float(np.std(values, ddof=0))
        cov = float(std / mean) if mean not in (0.0,) and np.isfinite(mean) else 0.0
        records.append(
            {
                "coicop_leaf": str(leaf) if leaf is not None else "",
                "country": str(country) if country is not None else "",
                "n": n,
                "unit_value_mean": mean,
                "unit_value_std": std,
                "cov": cov,
                "dimension_mix": _dimension_mix(group["basis"]),
                "n_suppressed_flag": bool(n < LOW_N_FLOOR),
            }
        )

    out = pd.DataFrame(records)[F5_SCHEMA]
    return out.astype(
        {
            "coicop_leaf": "object",
            "country": "object",
            "n": "int64",
            "unit_value_mean": "float64",
            "unit_value_std": "float64",
            "cov": "float64",
            "dimension_mix": "object",
            "n_suppressed_flag": "bool",
        }
    )


def _render_markdown(frame: pd.DataFrame, source: str) -> str:
    parts = [
        md.md_section("F5 — Within-Leaf Unit-Value Dispersion", 1),
        (
            f"Source: `{source}`. Unit-value dispersion per (COICOP leaf × "
            f"country). High CoV within a single-dimension cell flags a leaf "
            f"that may need a sub-label split (tier-b candidate). Cells with "
            f"n < {LOW_N_FLOOR} are flagged `n_suppressed_flag` (indicative "
            f"only). The machine table `{F5_PARQUET_NAME}` carries the locked "
            f"schema that downstream `build` re-reads as a comparison-validity "
            f"gate."
        ),
        md.md_section("Cells", 2),
        md.md_table(frame.to_dict("records"), columns=F5_SCHEMA),
    ]
    return "\n\n".join(parts)


def build_f5(
    frame: pd.DataFrame,
    source: str = "gold",
    write: bool = False,
):
    """Compute the F5 within-leaf dispersion table + Markdown report.

    `source="gold"` derives unit value from the canonical `val_gold` amount and
    the dimension from `basis_gold`. `source="corpus"` derives unit value from
    `price ÷ amount_value ÷ multiplier` via the spine and the dimension from the
    spine's `pricing_basis`.

    Returns `(frame, markdown)`. When `write=True`, also writes the locked-schema
    parquet and the Markdown under the harness report dir and returns a dict with
    `frame`, `markdown`, `parquet_path`, `markdown_path`.
    """
    if source == "gold":
        rows = _gold_rows(frame)
    elif source == "corpus":
        rows = _corpus_rows(frame)
    else:
        raise ValueError(f"source must be 'gold' or 'corpus': {source!r}")

    table = _aggregate(rows)
    markdown = _render_markdown(table, source)

    if not write:
        return table, markdown

    parquet_path = io.write_parquet(F5_PARQUET_NAME, table)
    markdown_path = io.write_markdown(F5_MARKDOWN_NAME, markdown)
    return {
        "frame": table,
        "markdown": markdown,
        "parquet_path": parquet_path,
        "markdown_path": markdown_path,
    }
