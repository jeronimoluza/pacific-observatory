"""`po prices weekly diff A B`: two per-country output trees, compared country by country.

A partition is one directory holding files under `<root>/<country>` (Stage B: the
country itself for food and `nonfood/`). Every file is compared byte for byte
first. A parquet whose bytes differ is then compared by rows, schema, key set
and one hash per column, read one column and one batch at a time so the large
countries (india, brazil, ukraine) stay small. Other files report how many lines
differ.

File verdicts: EQUAL (bytes), SAME_CONTENT (bytes differ, every column equal in
order), ROW_ORDER (same rows, other order), DIFF, ONLY_A, ONLY_B. A partition is
EQUAL when every file is EQUAL or SAME_CONTENT.
"""

from __future__ import annotations

import difflib
import filecmp
import hashlib
from pathlib import Path

import click
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

KEYS = {
    "observations.parquet": ["input_hash", "observation_date"],
    "trusted_observations.parquet": ["input_hash", "observation_date"],
    "product_months.parquet": ["input_hash", "month"],
}
BATCH = 1 << 20
OK = ("EQUAL", "SAME_CONTENT")


def _row_hashes(pf: pq.ParquetFile, columns: list[str]) -> np.ndarray:
    parts = []
    for batch in pf.iter_batches(columns=columns, batch_size=BATCH):
        df = batch.to_pandas()
        try:
            h = pd.util.hash_pandas_object(df, index=False)
        except TypeError:
            h = pd.util.hash_pandas_object(df.astype(str), index=False)
        parts.append(h.to_numpy())
    return np.concatenate(parts) if parts else np.empty(0, dtype=np.uint64)


def _col_digest(pf: pq.ParquetFile, col: str) -> tuple[str, int]:
    """(ordered digest, order-free sum of row hashes) for one column."""
    h = _row_hashes(pf, [col])
    return hashlib.blake2b(h.tobytes(), digest_size=16).hexdigest(), int(
        h.sum(dtype=np.uint64)
    )


def _cmp_parquet(a: Path, b: Path) -> tuple[str, str]:
    fa, fb = pq.ParquetFile(a), pq.ParquetFile(b)
    sa, sb = fa.schema_arrow.remove_metadata(), fb.schema_arrow.remove_metadata()
    na, nb = fa.metadata.num_rows, fb.metadata.num_rows
    notes = []
    if na != nb:
        notes.append(f"rows {na:,} vs {nb:,}")
    if not sa.equals(sb):
        only_a = [n for n in sa.names if n not in sb.names]
        only_b = [n for n in sb.names if n not in sa.names]
        typed = [
            n
            for n in sa.names
            if n in sb.names and sa.field(n).type != sb.field(n).type
        ]
        notes.append(f"schema only_a={only_a} only_b={only_b} type={typed}")
        if not (only_a or only_b or typed):
            notes.append("column order")
    common = [n for n in sa.names if n in sb.names]
    keys = [k for k in KEYS.get(a.name, ["input_hash"]) if k in common]
    if keys:
        ka, kb = np.unique(_row_hashes(fa, keys)), np.unique(_row_hashes(fb, keys))
        if not np.array_equal(ka, kb):
            notes.append(
                f"keys({'+'.join(keys)}) {len(ka):,} vs {len(kb):,}, "
                f"only_a={len(np.setdiff1d(ka, kb)):,} only_b={len(np.setdiff1d(kb, ka)):,}"
            )
        del ka, kb
    differ, reordered = [], []
    for col in common:
        oa, ua = _col_digest(fa, col)
        ob, ub = _col_digest(fb, col)
        if ua != ub:
            differ.append(col)
        elif oa != ob:
            reordered.append(col)
    if differ:
        more = ",..." if len(differ) > 8 else ""
        notes.append(
            f"columns differ {len(differ)}/{len(common)}: {','.join(differ[:8])}{more}"
        )
    if notes:
        return "DIFF", "; ".join(notes)
    if reordered:
        return (
            "ROW_ORDER",
            f"same rows, order differs in {len(reordered)}/{len(common)} columns",
        )
    return "SAME_CONTENT", "bytes differ, columns equal"


def _cmp_text(a: Path, b: Path) -> tuple[str, str]:
    la = a.read_text(errors="replace").splitlines()
    lb = b.read_text(errors="replace").splitlines()
    n = sum(
        1
        for line in difflib.unified_diff(la, lb, lineterm="", n=0)
        if line[:1] in "+-" and not line.startswith(("+++", "---"))
    )
    return "DIFF", f"{n} lines differ ({len(la)} vs {len(lb)} lines)"


def compare_file(a: Path, b: Path) -> tuple[str, str]:
    if not a.exists():
        return "ONLY_B", ""
    if not b.exists():
        return "ONLY_A", ""
    if filecmp.cmp(a, b, shallow=False):
        return "EQUAL", ""
    if a.suffix == ".parquet":
        return _cmp_parquet(a, b)
    return _cmp_text(a, b)


def _files(root: Path) -> set[Path]:
    return (
        {p.relative_to(root) for p in root.rglob("*") if p.is_file()}
        if root.is_dir()
        else set()
    )


def _obs_rows(d: Path) -> str:
    f = d / "observations.parquet"
    return f"{pq.ParquetFile(f).metadata.num_rows:,}" if f.exists() else "-"


def diff_country(a: Path, b: Path, country: str) -> list[tuple[str, str, list]]:
    """[(partition, verdict, [(file, verdict, detail)])] for one country."""
    fa, fb = _files(a / country), _files(b / country)
    if not fa and not fb:
        return [(".", "MISSING_BOTH", [])]
    out = []
    for part in sorted({f.parent for f in fa | fb}):
        names = sorted(f.name for f in fa | fb if f.parent == part)
        files = [
            (n, *compare_file(a / country / part / n, b / country / part / n))
            for n in names
        ]
        verdict = "EQUAL" if all(v in OK for _, v, _ in files) else "DIFF"
        out.append((str(part), verdict, files))
    return out


def diff_trees(a: Path, b: Path, countries: list[str] | None) -> int:
    if countries is None:
        countries = sorted({p.name for r in (a, b) for p in r.iterdir() if p.is_dir()})
    click.echo(f"A {a}\nB {b}\n{len(countries)} countries")
    click.echo(
        f"{'country':28s} {'part':10s} {'verdict':12s} {'obs A':>12s} {'obs B':>12s}"
    )
    equal = diff = 0
    for country in countries:
        for part, verdict, files in diff_country(a, b, country):
            label = "food" if part == "." else part
            ra, rb = _obs_rows(a / country / part), _obs_rows(b / country / part)
            click.echo(f"{country:28s} {label:10s} {verdict:12s} {ra:>12s} {rb:>12s}")
            if verdict == "EQUAL":
                equal += 1
                continue
            diff += 1
            for name, v, detail in files:
                if v not in OK:
                    click.echo(f"    {name:30s} {v:12s} {detail}")
    click.echo(f"EQUAL {equal} / DIFF {diff}")
    return 1 if diff else 0
