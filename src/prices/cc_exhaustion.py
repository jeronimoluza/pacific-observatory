"""Two exhaustion numbers per source, deliberately not blended into one.

The crawl axis and the record axis fail differently and have different fixes.
"97% of records parsed, 8% of crawls resolved" blends to about 50% and tells
you nothing true about either.

    crawl axis   crawls we got something from / crawls the host appears in
    record axis  rows parsed / (rows parsed + retryable residual)

**The crawl-axis denominator is a ceiling, not the real one, and stays that
way until resolve fills the ledger's negatives.** "Crawls the host appears in"
is knowable only by resolving against the index; disk cannot prove a host is
absent from a crawl, because absence has no filename. Dividing by every
published crawl therefore *understates* coverage for any host that genuinely
predates CC or has died: a source live for only three years can never exceed
~25% against a 127-crawl denominator however complete it is. So the number
this reports is a LOWER BOUND, and it is labelled as one rather than being
quietly presented as the answer.

The residual split is terminal vs retryable because that, not a percentage,
is what decides done: 100% of records will never parse -- WAF stubs, 404s and
pages with no product markup are terminal -- so a threshold picks an arbitrary
line. Green is crawl axis 100% AND every remaining record terminal.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import click
import pandas as pd

from prices.cc_ledger import DATA_DIR, ledger_path

# index.commoncrawl.org/collinfo.json, fetched 2026-09-16: CC-MAIN-2008-2009
# .. CC-MAIN-2026-34. The vault recorded 126 a month earlier, so this is a
# moving denominator and any "swept everything" claim has to be crawl-keyed.
PUBLISHED_CRAWLS = 127

GOT_SOMETHING = ("parsed", "fetched")


def report_path(data_root: Path) -> Path:
    return Path(data_root) / "_cc_ledger" / "exhaustion.parquet"


def build(
    ledger: pd.DataFrame, *, published_crawls: int = PUBLISHED_CRAWLS
) -> pd.DataFrame:
    """One row per source: both axes, plus the residual that explains them."""
    have = ledger[ledger.status.isin(GOT_SOMETHING)]
    parsed = ledger[ledger.status == "parsed"]
    # A crawl fetched but never parsed is the one residual disk can prove, and
    # it is retryable by definition: the bytes are already on this machine.
    unparsed = ledger[ledger.status == "fetched"]

    rows = []
    for source, grp in have.groupby("source"):
        p = parsed[parsed.source == source]
        u = unparsed[unparsed.source == source]
        parsed_rows = int(p["rows"].fillna(0).sum())
        retryable = int(u["records"].fillna(0).sum())
        crawls_done = grp.crawl_id.nunique()
        rows.append(
            {
                "source": source,
                "crawls_done": crawls_done,
                "crawls_published": published_crawls,
                "crawl_axis_lower": crawls_done / published_crawls,
                "crawls_parsed": p.crawl_id.nunique(),
                "crawls_fetched_unparsed": u.crawl_id.nunique(),
                "parsed_rows": parsed_rows,
                "residual_retryable": retryable,
                # Nothing records a terminal reason yet: the sweep does not
                # write failure rows. Reporting 0 would read as "no terminal
                # residual", which is a stronger claim than the data supports.
                "residual_terminal": None,
                "record_axis": (
                    parsed_rows / (parsed_rows + retryable)
                    if (parsed_rows + retryable)
                    else None
                ),
                "first_crawl": grp.crawl_id.min(),
                "last_crawl": grp.crawl_id.max(),
                "era_span_years": int(grp.crawl_year.max() - grp.crawl_year.min()) + 1,
            }
        )
    out = pd.DataFrame(rows)
    return out.sort_values("crawl_axis_lower", ascending=False).reset_index(drop=True)


def _bucket(n: int) -> str:
    for hi, label in ((0, "0"), (5, "1-5"), (10, "6-10"), (20, "11-20"),
                      (40, "21-40"), (60, "41-60"), (80, "61-80"), (100, "81-100")):
        if n <= hi:
            return label
    return "101-127"


@click.command("cc-exhaustion")
@click.option("--only", metavar="SOURCE", multiple=True, help="Limit to these sources.")
@click.option("--out", type=click.Path(path_type=Path), default=None)
@click.option(
    "--published-crawls", type=int, default=PUBLISHED_CRAWLS, show_default=True,
    help="Denominator ceiling. The published crawl count moves; pass today's.",
)
def cc_exhaustion_command(only: tuple, out: Optional[Path], published_crawls: int) -> None:
    """Per-source Common Crawl exhaustion, on two axes that are never blended."""
    root = DATA_DIR
    led = pd.read_parquet(ledger_path(root))
    if only:
        led = led[led.source.isin(only)]
    rep = build(led, published_crawls=published_crawls)
    target = Path(out) if out else report_path(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    rep.to_parquet(target, index=False)

    click.echo(f"{len(rep):,} sources -> {target}")
    click.echo(
        "crawl axis is a LOWER BOUND: the denominator is every published "
        f"crawl ({published_crawls}), not the crawls each host appears in, "
        "which needs resolve."
    )
    click.echo()
    click.echo("crawl-axis distribution (crawls covered -> sources):")
    dist = rep.crawls_done.map(_bucket).value_counts()
    for label in ("0", "1-5", "6-10", "11-20", "21-40", "41-60", "61-80",
                  "81-100", "101-127"):
        if label in dist:
            click.echo(f"  {label:>8} {dist[label]:>5}")
    click.echo()
    click.echo(
        f"median {rep.crawls_done.median():.0f}/{published_crawls} "
        f"({rep.crawl_axis_lower.median():.1%})  "
        f"mean {rep.crawls_done.mean():.2f} ({rep.crawl_axis_lower.mean():.1%})"
    )
    stuck = rep[rep.residual_retryable > 0]
    click.echo(
        f"{len(stuck)} source(s) hold {int(stuck.residual_retryable.sum()):,} "
        "fetched records that were never parsed -- retryable without refetching."
    )
