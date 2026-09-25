"""Rule check: what an extraction-rule change really did, before it merges.

Spec: `2026-09-24-source-local-regex-layer.md` step 5, built on the operating
model's "Fixing extraction issues automatically" parts 2-4 and rung 1a's scratch
diffs. Two modes:

- `source S`: S's rows extracted with and without S's patch
  (`regex_patterns/source/S/patch.py`). Nothing outside S can move, so this is
  the whole blast radius. Each changed row is attributed to the patch entries
  whose removal reverts it, and each entry is held to its declared Intent.
- `shared --base SRC [--cand SRC]`: a shared-rule change, extracted with two
  checkouts' code over the corpus (or over the rows a `--prefilter` regex picks,
  35 s instead of 71 min), held to a declaration given on the command line.

**Refused** (hard): a changed row outside the declaration -- another transition,
another country (shared), or more than 10x the declared rows; a `count` > 1
that becomes 1; a patch example (any source's) that is not a real row or that
the rule no longer moves.

**Flagged** (sent to model review, never refused alone): the change adds case
sensitivity (upper-casing the name changes the fields), or a food row's unit
value moves 3x or more. "Food" is COICOP 01 in the frozen classify output,
known only for rows that output has (`coicop_known` in the report). The review reads `review_sample.parquet`, stratified by
rule x country x transition with every flagged row included.

Read-only: writes a report directory, never the extraction table or a patch.
Reads the frozen classify output for COICOP only; nothing is rescored.
"""

from __future__ import annotations

import dataclasses
import json
import subprocess
import sys
import tempfile
import time
from multiprocessing import get_context
from pathlib import Path
from typing import Optional

import click
import pandas as pd
import pyarrow.compute as pc
import pyarrow.dataset as pads

from prices.enrich import config
from prices.enrich.regex_patterns import dict_view
from prices.enrich.stages import decisions_store
from prices.enrich.stages.extraction import EXTRACTION_FIELDS, _structural_fields
from prices.enrich.stages.merge import compute_unit_value
from prices.enrich.stages.prepare import _clean_url
from prices.enrich.versioning import input_hash

ROWS_REFUSE = 10  # op-model part 2: "10x the declared rows" is a refusal
UV_FLAG = 3.0  # op-model part 3; the cutoff is still to be measured
PATCH_CAP = 10  # Q7, provisional: more entries flags the source for a shared review
PER_STRATUM = 20
MAX_FLAGGED = 100
REPORT_DIR = config.ENRICH_DIR / "_rulecheck"

_IN = ["product_name_original", "category", "country", "lang", "details", "unit", "source"]
_READ = [*_IN, "input_hash", "price", "product_url", "currency"]
_SRC_ROOT = Path(__file__).resolve().parents[2]


# ── extraction, many ways ──────────────────────────────────────────────


def _work(args):
    rows, overrides, upper = args
    dict_view._OVERRIDES.update(overrides)
    try:
        return [
            _structural_fields(str(r[0]).upper() if upper else r[0], *r[1:]) for r in rows
        ]
    finally:
        dict_view._OVERRIDES.clear()


def extract_rows(
    df: pd.DataFrame, overrides: Optional[dict] = None, upper: bool = False, workers: int = 14
) -> pd.DataFrame:
    """Extraction fields for every row of `df` with the running code, aligned to
    its index. `overrides` maps a source to the PatternSet it should use."""
    rows = list(df[_IN].itertuples(index=False, name=None))
    args = overrides or {}
    if len(rows) < 20_000 or workers <= 1:
        out = _work((rows, args, upper))
    else:
        step = len(rows) // (workers * 8) + 1
        chunks = [(rows[i : i + step], args, upper) for i in range(0, len(rows), step)]
        with get_context("fork").Pool(workers) as pool:
            out = [f for part in pool.map(_work, chunks) for f in part]
    return pd.DataFrame(out, columns=EXTRACTION_FIELDS, index=df.index)


def _extract_with(src: Path, df: pd.DataFrame, workers: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(fields, fields of the upper-cased name) under another checkout's code."""
    with tempfile.TemporaryDirectory() as tmp:
        inp, outp = f"{tmp}/in.parquet", f"{tmp}/out.parquet"
        df[_IN].to_parquet(inp, index=False)
        subprocess.run(
            [sys.executable, str(_SRC_ROOT / "prices/enrich/_rulecheck_extract.py"),
             str(src), inp, outp, str(workers)],
            check=True,
        )
        a, b = pd.read_parquet(outp), pd.read_parquet(outp + ".upper")
    return a.set_axis(df.index), b.set_axis(df.index)


def _read_products(flt) -> pd.DataFrame:
    table = pads.dataset(config.PRODUCTS_INPUT_PARQUET).to_table(columns=_READ, filter=flt)
    return table.to_pandas()


def changed(a: pd.DataFrame, b: pd.DataFrame) -> pd.Series:
    same = (a == b) | (a.isna() & b.isna())
    return ~same.all(axis=1)


def transitions(old: pd.DataFrame, new: pd.DataFrame) -> pd.Series:
    return old["pricing_basis"].fillna("none") + " -> " + new["pricing_basis"].fillna("none")


def parse_expect(expect: str) -> set[str]:
    """`"item -> volume, count -> volume"` -> {"item -> volume", "count -> volume"}."""
    out = set()
    for part in expect.split(","):
        a, sep, b = part.partition("->")
        if not sep:
            raise click.BadParameter(f"expect {part!r} is not '<basis> -> <basis>'")
        out.add(f"{a.strip()} -> {b.strip()}")
    return out


def _pieces(f: pd.DataFrame) -> pd.Series:
    count = pd.to_numeric(f["count"], errors="coerce").fillna(1).clip(lower=1)
    mult = pd.to_numeric(f["multiplier"], errors="coerce").fillna(1).clip(lower=1)
    return count * mult


def _unit_values(df: pd.DataFrame, f: pd.DataFrame) -> pd.Series:
    return pd.Series(
        [
            compute_unit_value(p, b, a, c, m)
            for p, b, a, c, m in zip(
                df["price"], f["pricing_basis"], f["amount_value"], f["count"], f["multiplier"]
            )
        ],
        index=df.index,
        dtype="float64",
    )


def _prefold_hash(name, url, country, currency) -> str:
    """`input_hash` as it was before scope step 4 folded `source` into it."""
    url = _clean_url(url)
    if url:
        return input_hash({"product_name_original": str(name), "product_url": url})
    return input_hash(
        {"product_name_original": str(name), "country": str(country), "currency": str(currency)}
    )


def _coicop(df: pd.DataFrame) -> pd.Series:
    """COICOP from the frozen classify output, NaN where it has no row.

    That output predates `source` in `input_hash`, so it joins on the pre-fold
    key; rows added since it froze (new sources, landed CC rows) have none.
    """
    if df.empty:
        return pd.Series(dtype=object, index=df.index)
    codes = decisions_store.read(
        config.DECISIONS_HIERLEX_PARQUET,
        columns=["input_hash", "country", "coicop_code"],
        countries=sorted(df["country"].dropna().unique()),
    ).drop_duplicates(["input_hash", "country"])
    keys = pd.DataFrame({
        "input_hash": [
            _prefold_hash(*r)
            for r in df[["product_name_original", "product_url", "country", "currency"]]
            .itertuples(index=False)
        ],
        "country": df["country"].to_numpy(),
    })
    m = keys.merge(codes, on=["input_hash", "country"], how="left")
    return pd.Series(m["coicop_code"].to_numpy(), index=df.index)


# ── judging one diff ───────────────────────────────────────────────────


def judge(df, old, new, old_up, new_up, strata: pd.Series) -> tuple[list[str], pd.DataFrame]:
    """Invariants over the changed rows of `df`. Returns (refusals, changed rows
    with old/new fields, unit values and flags)."""
    refusals = []
    rows = df.copy()
    for c in EXTRACTION_FIELDS:
        rows[f"{c}_old"], rows[f"{c}_new"] = old[c], new[c]
    rows["transition"] = transitions(old, new)
    rows["stratum"] = strata

    lost = (_pieces(old) > 1) & (_pieces(new) == 1)
    rows["count_lost"] = lost
    if lost.any():
        refusals.append(f"count > 1 became 1 on {int(lost.sum())} rows")

    rows["case_new"] = changed(new, new_up)
    rows["case_old"] = changed(old, old_up)
    rows["case_flag"] = rows["case_new"] & ~rows["case_old"]

    uv_old, uv_new = _unit_values(df, old), _unit_values(df, new)
    ratio = (uv_new / uv_old).where((uv_old > 0) & (uv_new > 0))
    rows["uv_old"], rows["uv_new"] = uv_old, uv_new
    rows["coicop_code"] = _coicop(df)
    rows["food"] = rows["coicop_code"].fillna("").astype(str).str.startswith("01")
    rows["uv_flag"] = rows["food"] & ((ratio >= UV_FLAG) | (ratio <= 1 / UV_FLAG))
    return refusals, rows


def review_sample(rows: pd.DataFrame) -> pd.DataFrame:
    """Up to PER_STRATUM rows per stratum x country x transition, plus every
    flagged row (capped), one row per distinct name."""
    rows = rows.drop_duplicates("product_name_original")
    keys = ["stratum", "country", "transition"]
    picked = rows.sample(frac=1, random_state=0).groupby(keys, dropna=False).head(PER_STRATUM)
    flagged = rows[rows["uv_flag"] | rows["case_flag"] | rows["count_lost"]].head(MAX_FLAGGED)
    out = pd.concat([picked, flagged])
    return out[~out.index.duplicated()]


def _write(kind: str, report: dict, rows: pd.DataFrame) -> Path:
    out = REPORT_DIR / kind / time.strftime("%Y%m%dT%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    rows.to_parquet(out / "changed.parquet")
    review_sample(rows).to_parquet(out / "review_sample.parquet")
    (out / "report.json").write_text(json.dumps(report, indent=2, default=str))
    return out


def _summary(rows: pd.DataFrame) -> dict:
    return {
        "changed_rows": len(rows),
        "transitions": rows["transition"].value_counts().to_dict(),
        "countries": rows["country"].value_counts().to_dict(),
        "count_lost": int(rows["count_lost"].sum()),
        "case_flag": int(rows["case_flag"].sum()),
        "uv_flag_food": int(rows["uv_flag"].sum()),
        "food_rows": int(rows["food"].sum()),
        "coicop_known": int(rows["coicop_code"].notna().sum()),
    }


# ── patches: examples, promotion, cap ──────────────────────────────────


def _patches() -> dict:
    root = Path(dict_view.__file__).parent / "source"
    names = sorted(d.name for d in root.iterdir() if d.is_dir() and d.name != "__pycache__")
    return {s: p for s in names if (p := dict_view.load_source_patch(s)) is not None}


def _without(patch, key):
    return dataclasses.replace(
        patch,
        additions=tuple(p for p in patch.additions if p.id != key),
        removals=tuple(r for r in patch.removals if r != key),
        replacements=tuple(p for p in patch.replacements if p.id != key),
        flags=patch.flags - {key},
        intent={k: v for k, v in patch.intent.items() if k != key},
    )


def check_examples(patches: Optional[dict] = None) -> list[str]:
    """Every patch entry's examples are real rows of its source that the entry
    still moves, in a declared transition (Q10). Returns refusals."""
    patches = _patches() if patches is None else patches
    wanted = {(s, n) for s, p in patches.items() for i in p.intent.values() for n in i.examples}
    if not wanted:
        return []
    df = _read_products(
        pads.field("source").isin(sorted({s for s, _ in wanted}))
        & pads.field("product_name_original").isin(sorted({n for _, n in wanted}))
    ).drop_duplicates(["source", "product_name_original"])
    refusals = []
    for source, patch in patches.items():
        full = dict_view.compose(patch)
        for key, intent in patch.intent.items():
            ex = df[(df["source"] == source) & df["product_name_original"].isin(intent.examples)]
            missing = set(intent.examples) - set(ex["product_name_original"])
            if missing:
                refusals.append(f"{source}/{key}: examples not in its rows: {sorted(missing)}")
            if ex.empty:
                continue
            new = extract_rows(ex, {source: full}, workers=1)
            old = extract_rows(ex, {source: dict_view.compose(_without(patch, key))}, workers=1)
            still = changed(old, new)
            if not still.all():
                names = ex.loc[~still, "product_name_original"].tolist()
                refusals.append(f"{source}/{key}: no longer moves {names}")
            bad = set(transitions(old[still], new[still])) - parse_expect(intent.expect)
            if bad:
                refusals.append(f"{source}/{key}: examples move {sorted(bad)}, not {intent.expect!r}")
    return refusals


def _signature(p) -> tuple:
    ue = p.unit_emit
    return (p.kind, p.groups, p.pricing_basis_emit, p.fixed_count,
            (ue.basis, ue.su, ue.mul) if ue else None)


def scan_patches(patches: Optional[dict] = None) -> dict:
    """Promotion candidates (Q5) and over-cap sources (Q7). Opens reviews; edits nothing."""
    patches = _patches() if patches is None else patches
    over_cap = {
        s: n for s, p in patches.items()
        if (n := len(p.additions) + len(p.removals) + len(p.replacements) + len(p.flags)) > PATCH_CAP
    }
    countries: dict[str, set] = {}
    if patches:
        keys = _read_products(pads.field("source").isin(sorted(patches)))[["source", "country"]]
        for s, c in keys.drop_duplicates().itertuples(index=False):
            countries.setdefault(s, set()).add(c)
    same: dict[tuple, set] = {}
    for s, p in patches.items():
        for pat in (*p.additions, *p.replacements):
            same.setdefault(("regex", pat.regex.pattern, pat.regex.flags, _signature(pat)), set()).add(s)
        for pat in p.replacements:
            same.setdefault(("id", pat.id, _signature(pat)), set()).add(s)
    promotions = []
    for key, sources in same.items():
        cs = set().union(*(countries.get(s, set()) for s in sources))
        if len(sources) >= 2 and len(cs) >= 2:
            promotions.append({"match": key[0], "rule": key[1], "sources": sorted(sources),
                               "countries": sorted(cs)})
    return {"promotions": promotions, "over_cap": over_cap}


# ── the two modes ──────────────────────────────────────────────────────


def check_source(source: str, workers: int = 14) -> tuple[dict, Path]:
    patch = dict_view.load_source_patch(source)
    if patch is None:
        raise click.ClickException(f"{source!r} has no patch under regex_patterns/source/")
    df = _read_products(pads.field("source") == source)
    shared = {source: dict_view.compose(None)}
    new = extract_rows(df, workers=workers)
    old = extract_rows(df, shared, workers=workers)
    chg = changed(old, new)
    d, o, n = df[chg], old[chg], new[chg]

    # Attribution: the entries whose removal reverts the row.
    by_entry = {}
    for key in patch.intent:
        minus = extract_rows(d, {source: dict_view.compose(_without(patch, key))}, workers=workers)
        by_entry[key] = changed(minus, n)
    strata = pd.Series(
        [",".join(k for k, m in by_entry.items() if m[i]) or "(interaction)" for i in d.index],
        index=d.index,
    )
    refusals, rows = judge(
        d, o, n,
        extract_rows(d, shared, upper=True, workers=workers),
        extract_rows(d, upper=True, workers=workers),
        strata,
    )
    entries = {}
    for key, intent in patch.intent.items():
        mask = by_entry[key]
        seen = transitions(o[mask], n[mask]).value_counts().to_dict()
        undeclared = set(seen) - parse_expect(intent.expect)
        if undeclared:
            refusals.append(f"{key}: undeclared transitions {sorted(undeclared)}")
        if int(mask.sum()) > ROWS_REFUSE * max(intent.rows, 1):
            refusals.append(f"{key}: moved {int(mask.sum())} rows, declared ~{intent.rows}")
        entries[key] = {"rows": int(mask.sum()), "declared_rows": intent.rows,
                        "expect": intent.expect, "transitions": seen}
    refusals += check_examples()
    report = {
        "mode": "source", "source": source, "source_rows": len(df),
        "verdict": "refused" if refusals else "model_review",
        "refusals": refusals, "entries": entries, **_summary(rows), **scan_patches(),
    }
    return report, _write(source, report, rows)


def check_shared(
    base: Path, cand: Optional[Path], countries: list[str], expect: str, rows_declared: int,
    prefilter: Optional[str], workers: int = 14,
) -> tuple[dict, Path]:
    flt = None
    if prefilter:
        flt = pc.match_substring_regex(pads.field("product_name_original"), prefilter)
    df = _read_products(flt)
    old, old_up = _extract_with(base, df, workers)
    new, new_up = _extract_with(cand or _SRC_ROOT, df, workers)
    chg = changed(old, new)
    d = df[chg]
    refusals, rows = judge(
        d, old[chg], new[chg], old_up[chg], new_up[chg], pd.Series("shared", index=d.index)
    )
    outside = sorted(set(d["country"].dropna()) - set(countries))
    if outside:
        refusals.append(f"moved rows in {len(outside)} undeclared countries: {outside[:10]}")
    undeclared = set(rows["transition"]) - parse_expect(expect)
    if undeclared:
        refusals.append(f"undeclared transitions {sorted(undeclared)}")
    if len(d) > ROWS_REFUSE * max(rows_declared, 1):
        refusals.append(f"moved {len(d)} rows, declared ~{rows_declared}")
    if cand is None:  # examples run with the running code, which is the candidate
        refusals += check_examples()
    report = {
        "mode": "shared", "base": str(base), "cand": str(cand or _SRC_ROOT),
        "prefilter": prefilter, "candidate_rows": len(df),
        "declared": {"countries": countries, "expect": expect, "rows": rows_declared},
        "verdict": "refused" if refusals else "model_review",
        "refusals": refusals, **_summary(rows),
    }
    return report, _write("_shared", report, rows)


# ── CLI ────────────────────────────────────────────────────────────────


def _print(report: dict, out: Path) -> None:
    click.echo(json.dumps({k: v for k, v in report.items() if k != "transitions"}, indent=2, default=str))
    click.echo(f"report: {out}")
    if report.get("verdict") == "refused":
        sys.exit(1)


@click.group("rulecheck")
def rulecheck_group() -> None:
    """Check an extraction-rule change against its declared intent before it merges."""


@rulecheck_group.command("source")
@click.argument("source")
@click.option("--workers", default=14, show_default=True)
def source_command(source: str, workers: int) -> None:
    """Diff SOURCE's rows with and without its patch; judge every entry."""
    _print(*check_source(source, workers))


@rulecheck_group.command("shared")
@click.option("--base", required=True, type=click.Path(exists=True, path_type=Path),
              help="src/ root of the checkout before the change.")
@click.option("--cand", type=click.Path(exists=True, path_type=Path),
              help="src/ root after the change (default: this checkout).")
@click.option("--country", "countries", multiple=True, required=True)
@click.option("--expect", required=True, help="e.g. 'item -> volume, count -> volume'")
@click.option("--rows", "rows_declared", type=int, required=True)
@click.option("--prefilter", help="Regex on product_name_original limiting the rows diffed.")
@click.option("--workers", default=14, show_default=True)
def shared_command(base, cand, countries, expect, rows_declared, prefilter, workers) -> None:
    """Diff two checkouts' extraction; judge against the declaration."""
    _print(*check_shared(base, cand, list(countries), expect, rows_declared, prefilter, workers))


@rulecheck_group.command("scan")
def scan_command() -> None:
    """Examples re-check, promotion candidates and over-cap sources, over every patch."""
    report = {"example_refusals": check_examples(), **scan_patches()}
    click.echo(json.dumps(report, indent=2, default=str))
    if report["example_refusals"]:
        sys.exit(1)
