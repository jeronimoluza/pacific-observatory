"""`po prices discovery ...` -- the candidates store's command line."""

from __future__ import annotations

from pathlib import Path

import click

from prices.discovery.db import DEFAULT_DB, connect


@click.group("discovery")
@click.option(
    "--db",
    "db_path",
    type=click.Path(path_type=Path),
    default=DEFAULT_DB,
    show_default=True,
    help="Discovery SQLite file.",
)
@click.pass_context
def discovery_group(ctx: click.Context, db_path: Path) -> None:
    """Find price sources with daily search budgets; track candidates to onboarding."""
    ctx.obj = {"db_path": db_path}


@discovery_group.command("seed")
@click.pass_context
def seed_command(ctx: click.Context) -> None:
    """Load countries, onboarded config domains, engines and skill inventories."""
    from prices.discovery.seed import seed_countries_and_configs, seed_inventories

    con = connect(ctx.obj["db_path"])
    with con:
        cfg = seed_countries_and_configs(con)
        inv = seed_inventories(con)
    click.echo(
        f"country dirs: {cfg['country_dirs']}  countries: {cfg['countries']}  configs read: {cfg['configs']}"
    )
    click.echo(f"onboarded (country, domain) pairs: {cfg['onboarded_pairs']}")
    click.echo(
        f"countries with no YAML ({len(cfg['empty_countries'])}): {', '.join(cfg['empty_countries'])}"
    )
    click.echo(f"inventory rows inserted: {inv['inventory_inserted']}  {inv['by_status']}")
    if inv["unmatched"]:
        click.echo(f"inventory files with no matching country dir: {', '.join(inv['unmatched'])}")


@discovery_group.command("status")
@click.option("--country", default=None, help="List one country's candidates.")
@click.pass_context
def status_command(ctx: click.Context, country: str | None) -> None:
    """Candidate counts by status, engine budgets, or one country's rows."""
    con = connect(ctx.obj["db_path"])
    if country:
        for r in con.execute(
            "SELECT status, domain, source_config, reason FROM candidates WHERE country = ? ORDER BY status, domain",
            (country,),
        ):
            click.echo(
                f"{r['status']:<14} {r['domain']:<40} {r['source_config'] or r['reason'] or ''}"
            )
        return
    n_countries = con.execute("SELECT COUNT(*) FROM countries").fetchone()[0]
    click.echo(f"countries: {n_countries}")
    for r in con.execute(
        "SELECT status, COUNT(*) n FROM candidates GROUP BY status ORDER BY n DESC"
    ):
        click.echo(f"  {r['status']:<14} {r['n']}")
    click.echo("engines:")
    for r in con.execute(
        "SELECT engine, daily_cap, parked_until FROM engines ORDER BY daily_cap DESC, engine"
    ):
        parked = f"  parked until {r['parked_until']}" if r["parked_until"] else ""
        click.echo(f"  {r['engine']:<12} cap {r['daily_cap']}{parked}")


@discovery_group.command("load-bank")
@click.argument("countries", nargs=-1, required=True)
@click.option("--show", is_flag=True, help="Print every expanded query.")
@click.pass_context
def load_bank_command(ctx: click.Context, countries: tuple[str, ...], show: bool) -> None:
    """Validate banks/<country>.yaml, expand it and insert its queries (idempotent)."""
    from prices.discovery.bank import load_bank

    con = connect(ctx.obj["db_path"])
    failed = False
    for country in countries:
        with con:
            res = load_bank(con, country)
        if res["errors"]:
            failed = True
            click.echo(f"{country}: NOT LOADED")
            for err in res["errors"]:
                click.echo(f"  - {err}")
            continue
        qs = res["queries"]
        by_lang: dict[str, int] = {}
        for q in qs:
            by_lang[q["lang"]] = by_lang.get(q["lang"], 0) + 1
        n_top = sum(q["tier"] == "top20" for q in qs)
        click.echo(
            f"{country}: {len(qs)} queries ({n_top} top20), {res['inserted']} new, by lang {by_lang}"
        )
        if show:
            for q in qs:
                click.echo(f"  {q['tier']:<6} {q['lang']:<4} {q['template']:<24} {q['text']}")
    if failed:
        raise SystemExit(1)


@discovery_group.command("search")
@click.option("--engines", default="yahoo,duckduckgo,yandex,google", show_default=True)
@click.option("--country", default=None, help="Only this country's queries.")
@click.option("--limit", type=int, default=None, help="At most this many queries per engine.")
@click.pass_context
def search_command(
    ctx: click.Context, engines: str, country: str | None, limit: int | None
) -> None:
    """Run ddgs queries until each engine's daily cap, a block, or --limit."""
    from prices.discovery.search import run_ddgs

    con = connect(ctx.obj["db_path"])
    totals = run_ddgs(con, engines.split(","), country=country, limit=limit, echo=click.echo)
    for engine, stats in totals.items():
        click.echo(f"{engine}: {stats}")


@discovery_group.command("triage")
@click.option("--country", default=None)
@click.option("--limit", type=int, default=None)
@click.option(
    "--workers", type=int, default=6, show_default=True, help="Sites fetched in parallel."
)
@click.pass_context
def triage_command(
    ctx: click.Context, country: str | None, limit: int | None, workers: int
) -> None:
    """Fetch <= 3 pages per `discovered` candidate and set its verdict."""
    from prices.discovery.triage import run_triage

    con = connect(ctx.obj["db_path"])
    tally = run_triage(con, country=country, limit=limit, workers=workers, echo=click.echo)
    click.echo(f"verdicts: {dict(tally)}")


@discovery_group.command("queue")
@click.option("--engine", default="websearch", show_default=True)
@click.option("--n", "n", type=int, default=None, help="Default: what is left of today's cap.")
@click.option("--country", default=None)
@click.pass_context
def queue_command(ctx: click.Context, engine: str, n: int | None, country: str | None) -> None:
    """Print the next queries for an engine: query_id, country, text."""
    from prices.discovery.search import budget_left, next_queries

    con = connect(ctx.obj["db_path"])
    left = budget_left(con, engine)
    click.echo(f"# {engine}: {left} left today")
    for q in next_queries(con, engine, min(left, n if n is not None else left), country):
        click.echo(f"{q['query_id']}\t{q['country']}\t{q['text']}")


@discovery_group.group("record")
def record_group() -> None:
    """Write what a Claude session found: WebSearch runs, verdicts, follow-ups."""


@record_group.command("search")
@click.argument("query_id")
@click.argument("hits_json", type=click.Path(exists=True, path_type=Path))
@click.option("--engine", default="websearch", show_default=True)
@click.pass_context
def record_search_command(ctx: click.Context, query_id: str, hits_json: Path, engine: str) -> None:
    """Record one search: HITS_JSON is a list of {url, title, snippet}."""
    import json

    from prices.discovery.search import budget_left, record_run

    con = connect(ctx.obj["db_path"])
    q = con.execute("SELECT * FROM queries WHERE query_id = ?", (query_id,)).fetchone()
    if q is None:
        raise click.ClickException(f"no query {query_id}; add one with `record followup`")
    if con.execute(
        "SELECT 1 FROM runs WHERE query_id = ? AND engine = ? AND status != 'error'",
        (query_id, engine),
    ).fetchone():
        raise click.ClickException(f"{query_id} already ran on {engine}")
    if budget_left(con, engine) <= 0:
        raise click.ClickException(f"{engine} has no budget left today")
    hits = json.loads(hits_json.read_text(encoding="utf-8"))
    with con:
        res = record_run(con, q, engine, "ok" if hits else "empty", hits)
    click.echo(
        f"{query_id}: {len(hits)} hits, {res['new']} new candidates, {res['blocklisted']} blocklisted"
    )


@record_group.command("verdict")
@click.argument("country")
@click.argument("domain")
@click.argument(
    "status",
    type=click.Choice(["verified", "rejected", "ambiguous", "blocked_plain", "blocked_hard"]),
)
@click.option("--reason", required=True)
@click.option(
    "--kind", type=click.Choice(["retail", "tariff", "bulletin", "classifieds"]), default=None
)
@click.pass_context
def record_verdict_command(
    ctx: click.Context, country: str, domain: str, status: str, reason: str, kind: str | None
) -> None:
    """Settle a `discovered` or `ambiguous` candidate."""
    from prices.discovery.triage import _now

    con = connect(ctx.obj["db_path"])
    with con:
        cur = con.execute(
            """UPDATE candidates SET status = ?, reason = ?, kind = COALESCE(?, kind), updated_at = ?
               WHERE country = ? AND domain = ? AND status IN ('discovered', 'ambiguous')""",
            (status, reason, kind, _now(), country, domain),
        )
    if not cur.rowcount:
        raise click.ClickException(f"no discovered/ambiguous candidate ({country}, {domain})")
    click.echo(f"{country} {domain} -> {status}")


@record_group.command("followup")
@click.argument("country")
@click.argument("text")
@click.option("--lang", default="en", show_default=True)
@click.option("--template", default=None, help="Kind hint, e.g. supermarket_city or fuel_price.")
@click.pass_context
def record_followup_command(
    ctx: click.Context, country: str, text: str, lang: str, template: str | None
) -> None:
    """Add a follow-up query; it prints the id to use with `record search`."""
    from prices.discovery.bank import query_id
    from prices.discovery.triage import _now

    con = connect(ctx.obj["db_path"])
    qid = query_id(country, text)
    with con:
        cur = con.execute(
            """INSERT OR IGNORE INTO queries (query_id, country, text, lang, template, tier, origin, created_at)
               VALUES (?, ?, ?, ?, ?, 'followup', 'claude', ?)""",
            (qid, country, text, lang, template, _now()),
        )
    click.echo(f"{qid}\t{'added' if cur.rowcount else 'exists'}")
