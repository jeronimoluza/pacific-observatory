"""Text publish stage: generate EPU dashboards and charts."""

from pathlib import Path

import click

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "text"


def _discover_countries(region=None, country=None):
    """Find country directories under outputs/text/ that have EPU data."""
    if not OUTPUT_DIR.exists():
        return []

    candidates = sorted(
        d.name
        for d in OUTPUT_DIR.iterdir()
        if d.is_dir() and (d / "epu" / "epu.csv").exists()
    )

    if country:
        requested = {c.strip().lower() for c in country.split(",")}
        candidates = [c for c in candidates if c.lower() in requested]

    return candidates


def _load_dashboard_data(countries):
    """Load topic attribution, topics EPU, and actors EPU data for dashboard."""
    from text.plotting.small_dashboard_integrated import (
        df_to_json,
        load_actors_epu_data,
        load_attribution_data,
        load_topics_epu_data,
    )

    topic_data = {}
    for c in countries:
        df = load_attribution_data(c, OUTPUT_DIR, "topics")
        if df is not None:
            topic_data[c] = df_to_json(df)

    topics_data = {}
    topics_set = set()
    for c in countries:
        df = load_topics_epu_data(c, OUTPUT_DIR)
        if df is not None:
            topics_data[c] = df_to_json(df)
            topics_set.update(
                col.replace("EPU_", "").replace("_index", "")
                for col in df.columns
                if col.startswith("EPU_") and col.endswith("_index")
            )

    topics_items = sorted(topics_set)
    topics_defaults = [
        "inflation_prices",
        "energy",
        "diesel",
        "oil",
        "natural_gas",
        "fuel_rationing",
    ]
    topics_defaults = [t for t in topics_defaults if t in topics_items]
    if not topics_defaults:
        topics_defaults = topics_items[:5]

    actors_data = {}
    actors_set = set()
    for c in countries:
        df = load_actors_epu_data(c, OUTPUT_DIR)
        if df is not None:
            actors_data[c] = df_to_json(df)
            for col in df.columns:
                if col.startswith("EPU_") and col.endswith("_index"):
                    actors_set.add(col[4:-6])

    actors_items = sorted(actors_set)
    actors_defaults = [
        "central_bank",
        "parliament",
        "government",
        "world_bank",
        "international_organizations",
    ]
    actors_defaults = [a for a in actors_defaults if a in actors_items]
    if not actors_defaults:
        actors_defaults = actors_items[:5]

    return (
        topic_data,
        topics_data,
        topics_items,
        topics_defaults,
        actors_data,
        actors_items,
        actors_defaults,
    )


def run_publish(region=None, country=None, yes=False):
    """Generate EPU dashboards."""
    countries = _discover_countries(region=region, country=country)

    click.echo()
    click.echo("  Text publish (dashboards)")
    click.echo("  " + "-" * 40)
    click.echo(f"  Countries: {', '.join(countries) if countries else '(none found)'}")
    click.echo()

    if not countries:
        click.echo("  No countries with EPU data found. Run 'po text build' first.")
        return

    if not yes:
        click.confirm("  Proceed?", abort=True)

    (
        topic_data,
        topics_data,
        topics_items,
        topics_defaults,
        actors_data,
        actors_items,
        actors_defaults,
    ) = _load_dashboard_data(countries)

    missing = []
    if not topic_data:
        missing.append("uncertainty attribution (topics)")
    if not topics_data:
        missing.append("topics EPU")
    if not actors_data:
        missing.append("actors EPU")
    if missing:
        click.echo(f"  Missing data for: {', '.join(missing)}")
        click.echo("  Run 'po text build' first to generate the data.")
        return

    from text.plotting.small_dashboard_integrated import generate_dashboard

    generate_dashboard(
        OUTPUT_DIR,
        topic_data,
        topics_data,
        topics_items,
        topics_defaults,
        actors_data,
        actors_items,
        actors_defaults,
    )
