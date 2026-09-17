"""Did a source that used to return rows just return none?

A separate pass over the collect run files, not the write path. The three write
paths share no code before disk, so a write-path check means writing it twice or
building a seam 1,873 source adapters have to cross. It does not need one: the
history is already on disk and never pruned -- 17,341 run files across 2,155
sources, median 4 runs each.

**Tier 1 is zero-after-nonzero, and nothing else.** A source whose newest run
came back empty when an earlier one did not is broken, with no false-positive
class: there is no legitimate reason for a source that produced rows last week
to produce none this week. Every other candidate rule has one. A flat row count
is a real killer and is NOT here, because fixed-snapshot sources and telecom
tariff pages are flat by design and the discriminator is source type, which is
not in the data. A run below some fraction of its own history needs a threshold,
and a threshold needs a hand-triaged sample before it can ship a number.

**A run is a file, and an empty run is an empty file.** Measured on the live
corpus: 3,327 of the 17,341 run files are exactly zero bytes and NOT ONE file
falls between 1 and 200 bytes, so the zero boundary is crisp and `stat` decides
it. That is why this reads 17,341 directory entries rather than 29 GB of JSONL.

**Records loudly, changes nothing.** No quarantine, no blocking, no rerun. A
false positive that quarantined a good run would be worse than today's silence;
escalate to blocking only once the false-positive rate is known from real runs.
The one concession to automation is the exit code.

The fetcher rule and tier 2 belong in this module when they land, sharing the
verdict type and the ledger emission -- splitting them duplicates both halves.
A fetcher appends one row per run, so a ratio rule reads it as broken forever on
a healthy source; it needs its own rule against declared cadence, and thresholds
calibrated against a hand-triaged sample first.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

import click

from prices import lineage
from prices.partition import compile_selector

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "prices"

# `<source>_<YYYYMMDD>_<HHMMSS>.jsonl`. The stamp sorts lexicographically in
# time order, which is the only ordering this needs -- it never does date
# arithmetic, so it never has to parse one.
RUN_STAMP = re.compile(r"_(\d{8}_\d{6})\.jsonl$")

RUN_DIR = "raw_items"


@dataclass(frozen=True)
class Run:
    stamp: str
    path: Path
    n_bytes: int

    @property
    def empty(self) -> bool:
        return self.n_bytes == 0


@dataclass(frozen=True)
class SourceVerdict:
    """What one source's own run history says about its newest run."""

    key: str  # region/subregion/country/source
    n_runs: int
    latest: str
    n_empty_trailing: int  # consecutive empty runs ending at the newest
    last_nonempty: Optional[str]
    tier: int
    reason: str

    @property
    def flagged(self) -> bool:
        return self.tier > 0


def history(root: Optional[Path] = None) -> dict[str, list[Run]]:
    """Every source's runs, oldest first, keyed by partition path.

    A source with no `raw_items` directory is absent rather than empty: it has
    never run, which is a different thing from having run and returned nothing.
    """
    root = root or DATA_DIR
    out: dict[str, list[Run]] = {}
    for run_dir in root.glob("*/*/*/*/" + RUN_DIR):
        key = "/".join(run_dir.parent.relative_to(root).parts)
        runs = []
        for path in run_dir.glob("*.jsonl"):
            match = RUN_STAMP.search(path.name)
            if not match:
                continue
            try:
                runs.append(Run(match.group(1), path, path.stat().st_size))
            except OSError:  # vanished mid-walk; it cannot be judged
                continue
        if runs:
            out[key] = sorted(runs, key=lambda r: r.stamp)
    return out


def judge_source(key: str, runs: Sequence[Run]) -> SourceVerdict:
    """Tier 1 for one source: is the newest run empty when an older one was not?

    `n_empty_trailing` counts back from the newest rather than stopping at one,
    because a source empty for six runs and a source empty for one are the same
    verdict and very different problems.
    """
    n_empty_trailing = 0
    for run in reversed(runs):
        if not run.empty:
            break
        n_empty_trailing += 1
    nonempty = [r for r in runs if not r.empty]
    last_nonempty = nonempty[-1].stamp if nonempty else None

    if n_empty_trailing and last_nonempty:
        tier, reason = 1, "zero rows after a non-zero run"
    elif n_empty_trailing:
        # Never produced anything. Real, but it is an onboarding failure rather
        # than a regression, and it has no "before" to compare against.
        tier, reason = 0, "no run has ever produced a row"
    else:
        tier, reason = 0, "newest run produced rows"

    return SourceVerdict(
        key=key,
        n_runs=len(runs),
        latest=runs[-1].stamp,
        n_empty_trailing=n_empty_trailing,
        last_nonempty=last_nonempty,
        tier=tier,
        reason=reason,
    )


def judge(
    selectors: Optional[Sequence[str]] = None, root: Optional[Path] = None
) -> list[SourceVerdict]:
    """Every source matching `selectors`, worst first."""
    patterns = [compile_selector(s) for s in selectors] if selectors else None
    verdicts = [
        judge_source(key, runs)
        for key, runs in history(root).items()
        if patterns is None or any(p.match(key) for p in patterns)
    ]
    return sorted(verdicts, key=lambda v: (-v.tier, -v.n_empty_trailing, v.key))


@click.command("source-sanity")
@click.option(
    "--only",
    multiple=True,
    metavar="SELECTOR",
    help=(
        "Judge only part of the corpus. A selector is a glob over "
        "region/subregion/country/source. Repeatable."
    ),
)
def source_sanity_command(only: tuple[str, ...]) -> None:
    """Flag sources whose newest collect run came back empty after a full one."""
    verdicts = judge(list(only) or None)
    flagged = [v for v in verdicts if v.flagged]
    never = [v for v in verdicts if v.tier == 0 and v.n_empty_trailing]
    click.echo(
        f"{len(verdicts)} sources judged, {len(flagged)} tier 1 "
        f"(zero after non-zero), {len(never)} never produced a row"
    )
    for v in flagged:
        click.echo(
            f"  {v.key:60s} {v.n_empty_trailing:>3d} empty of {v.n_runs:<4d} "
            f"last good {v.last_nonempty}  newest {v.latest}"
        )
        lineage.record(
            "collect",
            "source_sanity.zero_after_nonzero",
            v.reason,
            scope=v.key,
            n_runs=v.n_runs,
            n_empty_trailing=v.n_empty_trailing,
            last_nonempty=v.last_nonempty,
            latest=v.latest,
        )
    # Non-zero exit is what lets the weekly collect notice without anyone
    # reading the log. It is the only thing this command changes.
    if flagged:
        raise SystemExit(1)
