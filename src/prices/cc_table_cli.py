"""Click commands for the Common Crawl columnar index scanner."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional, Tuple

import click

from prices import cc_table

logger = logging.getLogger(__name__)


@click.group("cc-table")
def cc_table_group() -> None:
    """Scan Common Crawl's Parquet index for known storefronts and new ones."""


@cc_table_group.command("scan")
@click.option(
    "--index",
    "indexes",
    multiple=True,
    required=True,
    help="CC index name like 'CC-MAIN-2026-30'. Repeatable.",
)
@click.option(
    "--keywords",
    "keywords_path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Newline-delimited product terms to match in url_path.",
)
@click.option(
    "--max-terms",
    type=int,
    default=None,
    help="Use only the first N terms of --keywords.",
)
@click.option(
    "--mode",
    type=click.Choice(["discover", "enumerate"]),
    required=True,
    help="discover = keyword-mine unknown storefronts (cheap projection, "
    "reads every row group). enumerate = pull WARC pointers for the "
    "storefronts that already have an archive_prefix.",
)
@click.option(
    "--threads",
    type=int,
    default=4,
    show_default=True,
    help="DuckDB threads per part. Each is a connection to data.commoncrawl.org; "
    "sustained load past ~12 gets the host 403'd.",
)
@click.option(
    "--passes",
    type=int,
    default=4,
    show_default=True,
    help="Sweep the pending parts this many times. Common Crawl 503s cold "
    "objects, so revisiting later beats retrying in place.",
)
@click.option(
    "--limit-parts",
    type=int,
    default=None,
    help="Scan only the first N of the crawl's 300 parts (calibration runs).",
)
def scan_command(
    indexes: Tuple[str, ...],
    keywords_path: Optional[Path],
    max_terms: Optional[int],
    mode: str,
    threads: int,
    passes: int,
    limit_parts: Optional[int],
) -> None:
    """Scan one or more crawls, resuming from each crawl's ledger."""
    domains: list = []
    keyword_regex = None
    if mode == "enumerate":
        domains = cc_table.known_domains()
        click.echo(f"enumerate: {len(domains)} known domains")
    else:
        if not keywords_path:
            raise click.UsageError("--mode discover requires --keywords")
        keyword_regex = cc_table.load_keyword_regex(keywords_path, max_terms)
        click.echo(f"discover: {keyword_regex.count('|') + 1} keyword terms")

    for index in indexes:
        click.echo(f"\n=== {index}")
        with click.progressbar(length=limit_parts or 300, label=index) as bar:
            summary = cc_table.scan_index(
                index,
                mode,
                domains=domains,
                keyword_regex=keyword_regex,
                threads=threads,
                limit_parts=limit_parts,
                passes=passes,
                progress=lambda _name, _rows: bar.update(1),
            )
        click.echo(
            json.dumps({k: v for k, v in summary.items() if k != "failed"}, indent=2)
        )
        if summary["parts_failed"]:
            click.echo(
                f"  {summary['parts_failed']} parts failed — rerun to retry them"
            )


@cc_table_group.command("candidates")
@click.option("--index", required=True, help="CC index whose hits to aggregate.")
@click.option(
    "--min-paths",
    type=int,
    default=3,
    show_default=True,
    help="Drop domains with fewer distinct matching paths.",
)
@click.option(
    "--min-terms",
    type=int,
    default=2,
    show_default=True,
    help="Drop domains that matched fewer distinct product terms.",
)
@click.option("--top", type=int, default=40, show_default=True, help="Rows to print.")
def candidates_command(index: str, min_paths: int, min_terms: int, top: int) -> None:
    """Aggregate keyword hits into a ranked list of unknown retailer domains."""
    out = cc_table.summarize_candidates(
        index,
        known_domains_list=cc_table.known_domains(),
        min_paths=min_paths,
        min_terms=min_terms,
    )
    click.echo(f"wrote {out}")
    import subprocess

    subprocess.run(
        [
            cc_table.duckdb_binary(),
            "-c",
            f"SELECT domain, tld, n_terms, n_paths, n_rows "
            f"FROM read_parquet('{out}') "
            f"ORDER BY n_terms DESC, n_paths DESC LIMIT {top};",
        ]
    )


@cc_table_group.command("triage")
@click.option("--index", required=True, help="CC index whose candidates to probe.")
@click.option(
    "--top",
    type=int,
    default=200,
    show_default=True,
    help="Probe the N highest-ranked candidate domains.",
)
@click.option(
    "--min-paths",
    type=int,
    default=3,
    show_default=True,
    help="Skip candidates with fewer distinct matching paths.",
)
@click.option(
    "--samples",
    type=int,
    default=3,
    show_default=True,
    help="Archived pages to fetch per candidate.",
)
@click.option(
    "--write-drafts",
    is_flag=True,
    help="Also stage a YAML manifest draft per usable candidate.",
)
def triage_command(
    index: str, top: int, min_paths: int, samples: int, write_drafts: bool
) -> None:
    """Fetch a few archived pages per candidate and see whether a price comes out."""
    from prices import cc_triage

    with click.progressbar(length=top, label="probing") as bar:
        out = cc_triage.triage_index(
            index,
            top=top,
            min_paths=min_paths,
            samples=samples,
            progress=lambda _domain, _n: bar.update(1),
        )
    click.echo(f"wrote {out}")

    rows = [json.loads(line) for line in Path(out).read_text().splitlines()]
    usable = [r for r in rows if r["usable"]]
    errored = [r for r in rows if r.get("errored")]
    live = [r for r in rows if r.get("live") is True]
    click.echo(
        f"\nprobed {len(rows)}   usable {len(usable)}   "
        f"live {len(live)} (scrapable now)   "
        f"with country {sum(1 for r in usable if r['country'])}   "
        f"errored {len(errored)} (retry these — not a verdict)"
    )
    for row in sorted(usable, key=lambda r: -r["n_terms"])[:30]:
        click.echo(
            f"  {row['domain']:<38} {str(row['country']):<22} "
            f"{row['n_paths']:>7} paths  {row['method']}  "
            f"{row['currency'] or ''} {row['sample_price'] or ''}"
        )

    if write_drafts:
        draft_dir = cc_triage.write_manifest_drafts(index)
        click.echo(f"\nmanifest drafts staged in {draft_dir}")
