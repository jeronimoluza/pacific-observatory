"""Display-only view of the §9 match-event logs (read-only consumer).

Turns the three long-format parquets written by `match_record.flush()`
(`match_log_long` / `suppression_log` / `residual_log`, under the gitignored
`_match_record/` dir) into a plain-text per-row trace a reviewer can eyeball:
which regex fired on which span, which candidate won at rank N, which one was
suppressed and why, and what residual text is left over.

This module is a pure consumer — it imports no recording path, triggers no
cascade behaviour, and writes nothing under data/ or outputs/. It only reads
the gitignored logs and prints. The metric/HTML dashboard (§5/§8) is Phase 1.7.
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from prices.enrich.config import ENRICH_DIR

DEFAULT_DIR = ENRICH_DIR / "_match_record"

PRODUCE_CMD = "PRICES_MATCH_RECORD=1 poetry run python run.py prices eval --no-write"

_FILES = {
    "match": "match_log_long.parquet",
    "suppression": "suppression_log.parquet",
    "residual": "residual_log.parquet",
}


def load_logs(log_dir, *, row=None, country=None, reason=None, shape=None):
    """Read the three §9 parquets from `log_dir` into filtered DataFrames.

    Returns `(match_df, suppression_df, residual_df)` or `None` when any of the
    three logs is absent (the caller prints the produce hint and exits cleanly).
    Filters are applied only on columns that exist in the real logs.
    """
    import pandas as pd

    log_dir = Path(log_dir)
    frames = {}
    for key, fname in _FILES.items():
        path = log_dir / fname
        if not path.exists():
            return None
        frames[key] = pd.read_parquet(path)

    match_df = frames["match"]
    suppression_df = frames["suppression"]
    residual_df = frames["residual"]

    if row is not None:
        rid = int(row)
        match_df = match_df[match_df["row_id"] == rid]
        suppression_df = suppression_df[suppression_df["row_id"] == rid]
        residual_df = residual_df[residual_df["row_id"] == rid]

    if country is not None and "country" in residual_df.columns:
        residual_df = residual_df[residual_df["country"] == country]
        keep = set(residual_df["row_id"])
        match_df = match_df[match_df["row_id"].isin(keep)]
        suppression_df = suppression_df[suppression_df["row_id"].isin(keep)]

    if reason is not None:
        sup_rows = set(
            suppression_df.loc[suppression_df["suppression_reason"] == reason, "row_id"]
        )
        sup_rows |= set(
            match_df.loc[match_df["suppression_reason"] == reason, "row_id"]
        )
        residual_df = residual_df[residual_df["row_id"].isin(sup_rows)]
        match_df = match_df[match_df["row_id"].isin(sup_rows)]
        suppression_df = suppression_df[suppression_df["row_id"].isin(sup_rows)]

    if shape is not None and "shape" in residual_df.columns:
        residual_df = residual_df[residual_df["shape"] == shape]
        keep = set(residual_df["row_id"])
        match_df = match_df[match_df["row_id"].isin(keep)]
        suppression_df = suppression_df[suppression_df["row_id"].isin(keep)]

    return match_df, suppression_df, residual_df


def _fmt_num(v):
    import pandas as pd

    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _fmt_span(start, end):
    import pandas as pd

    if start is None or end is None or pd.isna(start) or pd.isna(end):
        return ""
    return f"[{int(start)}:{int(end)}]"


def _candidate_sort_key(rec):
    import pandas as pd

    start = rec.get("start_char")
    start_key = float("inf") if start is None or pd.isna(start) else float(start)
    rank = rec.get("priority_rank")
    rank_key = float("inf") if rank is None or pd.isna(rank) else float(rank)
    return (start_key, rank_key)


def render_row(row_id, match_rows, suppression_rows, residual_row):
    """Build the plain-text trace block for one row (pure, no I/O).

    `match_rows` / `suppression_rows` are lists of dicts (match_log_long /
    suppression_log records for this row_id); `residual_row` is the single
    residual_log dict (or None). Marks the accepted candidate with ✓ and its
    priority_rank, suppressed candidates with ✗ and their non-null reason.
    """
    lines = [f"ROW {row_id}"]
    if residual_row is not None:
        lines.append(f"  raw:     {residual_row.get('raw_name')}")
        lines.append(f"  working: {residual_row.get('working_name')}")
        shape = residual_row.get("shape")
        if shape is not None:
            mods = json.loads(residual_row.get("modifiers") or "[]")
            mod_suffix = "".join(f" +{m}" for m in mods)
            lines.append(f"  shape:   {shape}{mod_suffix}")

    lines.append("  candidates:")
    for rec in sorted(match_rows, key=_candidate_sort_key):
        accepted = bool(rec.get("accepted"))
        suppressed = bool(rec.get("suppressed"))
        marker = "✓" if accepted else ("✗" if suppressed else "·")
        rank = rec.get("priority_rank")
        rank_str = f"rank{int(rank)}" if accepted and rank is not None else "rank-"
        regex_id = str(rec.get("regex_id") or "")
        text = rec.get("matched_text")
        text_str = f'"{text}"' if text is not None else '""'
        span = _fmt_span(rec.get("start_char"), rec.get("end_char"))
        parts = [
            f"    {marker} {rank_str:<6} {regex_id:<16} {text_str} {span}".rstrip()
        ]
        attrs = []
        basis = rec.get("candidate_basis")
        if basis is not None:
            attrs.append(f"basis={basis}")
        amt = _fmt_num(rec.get("candidate_amount"))
        if amt is not None:
            attrs.append(f"amt={amt}")
        unit = rec.get("candidate_unit")
        if unit is not None:
            attrs.append(f"unit={unit}")
        mult = _fmt_num(rec.get("candidate_multiplier"))
        if mult is not None:
            attrs.append(f"x{mult}")
        if suppressed:
            attrs.append(f"SUPPRESSED reason={rec.get('suppression_reason')}")
        line = parts[0]
        if attrs:
            line = f"{line}  {' '.join(attrs)}"
        lines.append(line)

    if suppression_rows:
        lines.append("  suppressions:")
        for rec in suppression_rows:
            regex_id = str(rec.get("regex_id") or "")
            text = rec.get("suppressed_text")
            span = _fmt_span(rec.get("start_char"), rec.get("end_char"))
            lines.append(
                f'    ✗ {regex_id:<16} "{text}" {span}'.rstrip()
                + f"  type={rec.get('suppression_type')}"
                + f" reason={rec.get('suppression_reason')}"
            )

    if residual_row is not None:
        lines.append(f"  residual: {residual_row.get('residual_text')}")
    return "\n".join(lines)


def render_summary(match_df, suppression_df, residual_df):
    """Build the compact summary header (pure, no I/O).

    Reports distinct row count, the accepted candidate basis distribution and
    the (more populated) accepted_source distribution, top regex_ids by fire
    count, suppression_reason counts, and the residual-changed rate.
    """
    lines = ["=== match-record summary ==="]
    n_rows = int(residual_df["row_id"].nunique())
    lines.append(f"rows: {n_rows}   candidate events: {len(match_df)}")

    accepted = match_df[match_df["accepted"] == True]  # noqa: E712
    lines.append("accepted candidate_basis:")
    basis_counts = accepted["candidate_basis"].value_counts(dropna=False)
    if basis_counts.empty:
        lines.append("  (none)")
    else:
        for val, cnt in basis_counts.items():
            pct = 100.0 * cnt / max(n_rows, 1)
            lines.append(f"  {str(val):<14} {cnt:>5}  ({pct:4.1f}%)")

    lines.append("accepted_source (winning rung):")
    src_counts = residual_df["accepted_source"].value_counts(dropna=False)
    for val, cnt in src_counts.items():
        pct = 100.0 * cnt / max(n_rows, 1)
        lines.append(f"  {str(val):<14} {cnt:>5}  ({pct:4.1f}%)")

    if "shape" in residual_df.columns:
        lines.append("shape distribution:")
        shape_counts = residual_df["shape"].value_counts(dropna=False)
        for val, cnt in shape_counts.items():
            pct = 100.0 * cnt / max(n_rows, 1)
            lines.append(f"  {str(val):<14} {cnt:>5}  ({pct:4.1f}%)")

    lines.append("top regex_id by fire count:")
    for val, cnt in match_df["regex_id"].value_counts().head(10).items():
        lines.append(f"  {str(val):<18} {cnt:>5}")

    lines.append("suppression_reason counts:")
    reason_counts = suppression_df["suppression_reason"].value_counts()
    if reason_counts.empty:
        lines.append("  (none)")
    else:
        for val, cnt in reason_counts.items():
            lines.append(f"  {str(val):<22} {int(cnt):>5}")

    changed = int((residual_df["residual_text"] != residual_df["working_name"]).sum())
    rate = 100.0 * changed / max(n_rows, 1)
    lines.append(f"residual changed (span stripped): {changed}/{n_rows} ({rate:4.1f}%)")
    return "\n".join(lines)


@click.command(name="match-record")
@click.option("--limit", type=int, default=20, help="Max per-row traces to print.")
@click.option("--row", "row", default=None, help="Render only this row_id.")
@click.option("--country", default=None, help="Filter to a country (if logged).")
@click.option(
    "--reason", default=None, help="Only rows carrying this suppression reason."
)
@click.option("--shape", default=None, help="Only rows with this primary shape.")
@click.option(
    "--dir",
    "log_dir",
    type=click.Path(file_okay=False),
    default=None,
    help="Override the log dir (default: data/prices/enrich/_match_record/).",
)
@click.option("--summary-only", is_flag=True, help="Print only the summary header.")
def match_record_command(limit, row, country, reason, shape, log_dir, summary_only):
    """Render a plain-text trace of the §9 match-event logs (read-only).

    Reads match_log_long / suppression_log / residual_log and prints a compact
    summary header plus a per-row candidate trace (pattern_id, span, accepted
    rank, suppression reason, residual). When the logs are absent it prints the
    command to produce them and exits cleanly. Writes nothing.
    """
    target = Path(log_dir) if log_dir else DEFAULT_DIR
    frames = load_logs(target, row=row, country=country, reason=reason, shape=shape)
    if frames is None:
        click.echo(f"no match-record logs found at {target}")
        click.echo(f"produce them with:\n  {PRODUCE_CMD}")
        return

    match_df, suppression_df, residual_df = frames
    if residual_df.empty:
        click.echo(f"no rows match the given filters at {target}")
        return

    click.echo(render_summary(match_df, suppression_df, residual_df))
    if summary_only:
        return

    click.echo("")
    row_ids = list(residual_df["row_id"])[:limit]
    for rid in row_ids:
        match_rows = match_df[match_df["row_id"] == rid].to_dict("records")
        suppression_rows = suppression_df[suppression_df["row_id"] == rid].to_dict(
            "records"
        )
        resid_recs = residual_df[residual_df["row_id"] == rid].to_dict("records")
        residual_row = resid_recs[0] if resid_recs else None
        click.echo(render_row(rid, match_rows, suppression_rows, residual_row))
        click.echo("")
