"""`po graph ledger`: the run ledger and the per-source budgets derived from it."""

from __future__ import annotations

from pathlib import Path

import click

from graph.ledger import budgets as B
from graph.ledger.store import BUDGETS, LEDGER_DIR, RAW_CACHE, RUNS

_dir_opt = click.option("--ledger-dir", type=click.Path(path_type=Path), default=LEDGER_DIR,
                        show_default=True, help="Where runs.parquet and source_budgets.parquet live.")


@click.group()
def ledger():
    """Run ledger (one row per pipeline, run_id, source) and per-source budgets."""


@ledger.command("ingest")
@_dir_opt
@click.option("--pipeline", type=click.Choice(["prices", "text", "all"]), default="all", show_default=True)
@click.option("--refresh", is_flag=True, help="Re-read runs already in the ledger.")
def ingest_cmd(ledger_dir, pipeline, refresh):
    """Read collect ledgers, logs, raw files and staged runs (read-only); append by run_id."""
    import pandas as pd

    from graph.ledger import store

    known = store.known_runs(ledger_dir)
    frames = []
    if pipeline in ("prices", "all"):
        from graph.ledger import prices

        df, cache = prices.ingest(known, store.read(RAW_CACHE, ledger_dir), refresh, log=click.echo)
        frames.append(df)
        store.write(cache, RAW_CACHE, ledger_dir)
    if pipeline in ("text", "all"):
        from graph.ledger import text

        frames.append(text.ingest(known, refresh, log=click.echo))
    new = pd.concat(frames, ignore_index=True)
    replaced, total = store.append_runs(new, ledger_dir)
    click.echo(f"{len(new)} filas nuevas ({new['run_id'].nunique()} run_id), {replaced} reemplazadas; "
               f"ledger {total} filas en {ledger_dir / RUNS}")


@ledger.command("budgets")
@_dir_opt
@click.option("-n", "n", default=B.N, show_default=True, help="Last N timed runs per source.")
@click.option("--margin", default=B.MARGIN, show_default=True, help="budget = p95 x margin.")
@click.option("--floor", "floor_s", default=B.FLOOR_S, show_default=True, help="Minimum budget (s).")
@click.option("--stall-min", default=B.STALL_MIN, show_default=True, help="Stalled = this many minutes without progress.")
@click.option("--top", default=10, show_default=True)
def budgets_cmd(ledger_dir, n, margin, floor_s, stall_min, top):
    """Derive p50/p95/budget, zero streaks and stalls per source; write source_budgets.parquet."""
    from graph.ledger import store

    runs = store.read(RUNS, ledger_dir)
    if runs is None:
        raise click.ClickException(f"no ledger at {ledger_dir / RUNS}; run `po graph ledger ingest`")
    df = B.derive(runs, n, margin, floor_s, stall_min)
    path = store.write(df, BUDGETS, ledger_dir)
    click.echo(f"{len(df)} fuentes -> {path}")
    cols = ["pipeline", "country", "source", "n_window", "p50_s", "p95_s", "budget_s", "censored",
            "zero_streak", "last_status"]
    for pipeline, g in df.groupby("pipeline"):
        click.echo(f"\n{pipeline}: {len(g)} fuentes, {int(g['budget_s'].notna().sum())} con presupuesto, "
                   f"{int(g['censored'].sum())} censuradas, {int(g['new_zero_streak'].sum())} en racha nueva de ceros, "
                   f"{int(g['over_budget'].sum())} sobre presupuesto, {int(g['stalled'].sum())} trabadas")
        click.echo(f"  más lentas (p95):\n{g.nlargest(top, 'p95_s')[cols].to_string(index=False)}")
        click.echo(f"  racha de ceros más larga:\n{g.nlargest(top, 'zero_streak')[cols].to_string(index=False)}")


@ledger.command("show")
@_dir_opt
@click.argument("source")
def show_cmd(ledger_dir, source):
    """Every run and the budget row of SOURCE (source name or country/source)."""
    import pandas as pd

    from graph.ledger import store

    runs = store.read(RUNS, ledger_dir)
    if runs is None:
        raise click.ClickException(f"no ledger at {ledger_dir / RUNS}")
    country, _, name = source.rpartition("/")
    hit = (runs["source"] == name) & ((runs["country"] == country) if country else True)
    cols = ["pipeline", "run_id", "country", "week", "start_utc", "duration_s", "new_rows", "status",
            "rc", "requests", "max_stall_s", "origin"]
    with pd.option_context("display.max_rows", None, "display.width", 220):
        click.echo(B.runs_in_order(runs[hit])[cols].to_string(index=False))
        b = store.read(BUDGETS, ledger_dir)
        if b is not None:
            bh = b[(b["source"] == name) & ((b["country"] == country) if country else True)]
            click.echo("\n" + bh.T.to_string(header=False))


@ledger.command("zeros")
@_dir_opt
@click.option("--week", default=None, help="Prices: silent zeros of this ISO week (graph.checks.raw_sources).")
@click.option("--last", default=2, show_default=True, help="Text: 0 rows in each of the last N staged runs.")
@click.option("-n", "n", default=4, show_default=True, help="Prices baseline weeks.")
@click.option("--list", "show", is_flag=True)
def zeros_cmd(ledger_dir, week, last, n, show):
    """Prices --week: silent zeros by graph.checks.raw_sources. Text: zero runs from the ledger."""
    from graph.ledger import store

    if week:
        df = B.silent_zeros(week, n)
        red = int((df["color"] == "rojo").sum())
        click.echo(f"prices {week}: {red} ceros silenciosos (rojo de graph.checks.raw_sources, baseline {n} semanas); "
                   f"{len(df) - red} fetchers sin delta (amarillo)")
    else:
        runs = store.read(RUNS, ledger_dir)
        ids, df = B.zero_runs(runs, last)
        click.echo(f"text {', '.join(ids)}: {len(df)} fuentes con 0 filas en las {len(ids)} corridas; "
                   f"por estados {df['statuses'].value_counts().to_dict()}")
    if show:
        click.echo(df.to_string(index=False))
