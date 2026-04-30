import sys
from pathlib import Path

import click


def command_prefix():
    return "python run.py" if Path(sys.argv[0]).name == "run.py" else "po"


def render_home():
    """Print the CLI home screen with optional cached snapshot."""
    import importlib.metadata

    try:
        version = importlib.metadata.version("pacific-observatory")
    except importlib.metadata.PackageNotFoundError:
        version = "dev"

    from text.status import read_status_cache

    cache = read_status_cache()

    lines = [
        "",
        f"  Pacific Observatory CLI v{version}",
        "",
        f"  Repo-local: {command_prefix()}",
        "  Installed alias: po",
        "",
        "  Pipelines:",
        f"    {command_prefix()} text      Newspaper scraping and EPU analysis",
        f"    {command_prefix()} fuel      [not migrated]",
        f"    {command_prefix()} prices    [not migrated]",
        "",
    ]

    if cache:
        computed_at = cache.get("computed_at", "unknown")
        lines.append(
            f"  Snapshot (computed {computed_at} — run '{command_prefix()} status' to refresh):"
        )

        text = cache.get("text", {})
        collect = text.get("collect", {})
        scraped = collect.get("sources_scraped", 0)
        total = collect.get("sources_total", 0)
        articles = collect.get("articles_total", 0)
        art_str = f"{articles / 1000:.0f}k" if articles >= 1000 else str(articles)
        last = collect.get("last_scraped_at", "—") or "—"

        lines.append(
            f"    text    {scraped}/{total} sources scraped · "
            f"{art_str} articles · last scraped {last}"
        )
        lines.append("    fuel    [not migrated]")
        lines.append("    prices  [not migrated]")
    else:
        lines.append("  Snapshot:")
        lines.append(f"    (no data — run '{command_prefix()} status')")

    lines.extend(
        [
            "",
            "  Start Here:",
            f"    {command_prefix()} list-regions                             Show region/subregion/country topology",
            f"    {command_prefix()} text collect --list --country <slug>     List configured newspaper keys",
            f"    {command_prefix()} text collect --country <slug> --dry-run  Preview a scrape safely",
            "",
            "  Typical Workflow:",
            f"    {command_prefix()} text collect --country <slug>            Scrape a single country",
            f"    {command_prefix()} text build --country <slug>              Compute EPU outputs",
            f"    {command_prefix()} text publish --country <slug>            Generate dashboards",
        ]
        + [
            "",
            "  Filters:  -r/--region  -S/--subregion  -c/--country  -s/--source (newspaper key)",
            "",
        ]
    )
    click.echo("\n".join(lines))


def _example_lines(title, commands):
    lines = [f"  {title}:"]
    for command, description in commands:
        lines.append(f"    {command_prefix()} {command:<40} {description}")
    return lines


def top_level_help_examples():
    return "\n".join(
        ["\b"]
        + _example_lines(
            "Start Here",
            [
                ("list-regions", "Show region/subregion/country topology"),
                (
                    "text collect --list --country <slug>",
                    "List configured newspaper keys",
                ),
                ("text collect --country <slug> --dry-run", "Preview a scrape safely"),
            ],
        )
    )


def text_help_examples():
    return "\n".join(
        ["\b"]
        + _example_lines(
            "Start Here",
            [
                (
                    "text collect --list --country <slug>",
                    "List configured newspaper keys",
                ),
                ("text collect --country <slug> --dry-run", "Preview a scrape safely"),
            ],
        )
        + _example_lines(
            "Typical Workflow",
            [
                ("text collect --country <slug>", "Scrape a single country"),
                ("text build --country <slug>", "Compute EPU outputs"),
                (
                    "text build --region <r> --max-parallel-sources 4",
                    "Build a region with 4 sources annotated concurrently",
                ),
                ("text publish --country <slug>", "Generate dashboards"),
            ],
        )
    )
