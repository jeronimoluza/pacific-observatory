"""`po prices weekly diff-enrich A B`: the enrich outputs of two trees, country by country.

A and B are tree roots (a worktree, or an output tree on the 5TB) holding `outputs/`
and `data/prices/enrich/`. Per country it compares, with `diff.compare_file`:
the per-source shards (`outputs/prices/raw/_per_source/*/*/<c>/`), `_prepared`,
`_prepared_months`, `cache/classified_hierlex` and `cache/decisions_hierlex`.

`_hierlex_pred` is bucketed by name, not by country: its rows are split by the
`country` column and compared per country as (rows, order-free sum of row hashes),
one bucket at a time. Its `_pairs` are not compared: score rebuilds them from
whatever `_prepared` it ran over, so a panel tree's pairs hold only the panel.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import click
import numpy as np
import pandas as pd

from prices.weekly.diff import OK, compare_file

ENRICH = Path("data/prices/enrich")
SHARDS = Path("outputs/prices/raw/_per_source")
PRED = ENRICH / "_hierlex_pred"


def _country_files(root: Path, country: str) -> dict[str, Path]:
    out = {}
    for f in (root / SHARDS).glob(f"*/*/{country}/*.parquet"):
        out[f"shard/{f.name}"] = f
    for sub in ("_prepared", "_prepared_months"):
        for f in (root / ENRICH / sub).glob(f"*/*/{country}.parquet"):
            out[sub] = f
    for sub in ("classified_hierlex", "decisions_hierlex"):
        f = root / ENRICH / "cache" / sub / f"{country}.parquet"
        if f.exists():
            out[sub] = f
    return out


def _pred_digests(root: Path, countries: list[str]) -> dict[str, tuple[int, int]]:
    """country -> (rows, order-free uint64 sum of row hashes) over every pred bucket."""
    acc = {c: [0, np.uint64(0)] for c in countries}
    files = sorted((root / PRED).glob("*/pred_*.parquet"))
    for f in files:
        df = pd.read_parquet(f)
        df = df[df["country"].isin(countries)]
        if df.empty:
            continue
        try:
            h = pd.util.hash_pandas_object(df, index=False).to_numpy()
        except TypeError:
            h = pd.util.hash_pandas_object(df.astype(str), index=False).to_numpy()
        for c, idx in df.groupby("country", sort=False).indices.items():
            acc[c][0] += len(idx)
            acc[c][1] += h[idx].sum(dtype=np.uint64)
    click.echo(f"pred {root}: {len(files)} buckets")
    return {c: (n, int(s)) for c, (n, s) in acc.items()}


def diff_enrich(a: Path, b: Path, countries: list[str]) -> int:
    click.echo(f"A {a}\nB {b}\n{len(countries)} countries")
    pa, pb = _pred_digests(a, countries), _pred_digests(b, countries)
    verdicts: Counter = Counter()
    equal = diff = 0
    for c in countries:
        fa, fb = _country_files(a, c), _country_files(b, c)
        rows = []
        for name in sorted(set(fa) | set(fb)):
            v, detail = compare_file(
                fa.get(name, a / "-missing-"), fb.get(name, b / "-missing-")
            )
            rows.append((name, v, detail))
        if pa[c] == pb[c]:
            rows.append(("_hierlex_pred", "SAME_CONTENT", ""))
        else:
            rows.append(
                ("_hierlex_pred", "DIFF", f"rows {pa[c][0]:,} vs {pb[c][0]:,}")
            )
        nshard = sum(1 for n in fa if n.startswith("shard/"))
        bad = [r for r in rows if r[1] not in OK]
        verdicts.update(v for _, v, _ in rows)
        click.echo(
            f"{c:28s} {'EQUAL' if not bad else 'DIFF':6s} {len(rows)} files ({nshard} shards)"
        )
        if bad:
            diff += 1
            for name, v, detail in bad:
                click.echo(f"    {name:40s} {v:12s} {detail}")
        else:
            equal += 1
    click.echo("FILES " + " ".join(f"{v}={n}" for v, n in sorted(verdicts.items())))
    click.echo(f"EQUAL {equal} / DIFF {diff}")
    return 1 if diff else 0
