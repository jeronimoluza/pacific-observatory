"""Selecting a subset of the prices corpus by its on-disk partition.

`outputs/prices/raw/_per_source/<region>/<subregion>/<country>/<source>.<ext>`
is already a four-level partition, written by the concatenate stage. Nothing
here reshuffles it: a selector is a glob against that same tree, so one string
names a region, a subregion, a country or a single source depending on how many
segments it has.

    ssa                                 every source in ssa
    ssa/southern                        every source in the southern subregion
    ssa/southern/south_africa           every source in one country
    ssa/southern/south_africa/agmarknet one source
    **/agmarknet                        that source wherever it lives
    */*/ghana                           one country without naming its region

A selector shorter than four segments selects the whole subtree beneath it, so
a trailing `/**` is implicit and never needs to be typed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
PER_SOURCE_DIR = REPO_ROOT / "outputs" / "prices" / "raw" / "_per_source"

# Depth of the partition below PER_SOURCE_DIR: region/subregion/country/source.
PARTITION_DEPTH = 4
PARTITION_LEVELS = ("region", "subregion", "country", "source")

# Shard formats, most preferred first. Both are listed for the duration of the
# CSV-to-parquet migration; a directory holding both formats for the same source
# resolves to the parquet.
SHARD_SUFFIXES = (".parquet", ".csv")


@dataclass(frozen=True)
class Shard:
    """One per-source file and the partition coordinates it sits at."""

    path: Path
    region: str
    subregion: str
    country: str
    source: str

    @property
    def key(self) -> str:
        return f"{self.region}/{self.subregion}/{self.country}/{self.source}"

    @property
    def size(self) -> int:
        try:
            return self.path.stat().st_size
        except OSError:
            return 0


class SelectorError(ValueError):
    """A selector that cannot refer to any shard, however the tree looks."""


def shard_from_path(path: Path, root: Path) -> Optional[Shard]:
    """Build a Shard from a file inside `root`, or None if it does not sit at
    the partition depth or carries an unknown suffix."""
    if path.suffix not in SHARD_SUFFIXES:
        return None
    try:
        rel = path.relative_to(root)
    except ValueError:
        return None
    parts = rel.parts
    if len(parts) != PARTITION_DEPTH:
        return None
    # `_`-prefixed directories are the pipeline's own scratch, not partitions —
    # the same convention concatenate's source walk uses. Without this an output
    # tree written beneath the root reads back as corpus on the next pass.
    if any(part.startswith("_") for part in parts):
        return None
    region, subregion, country, filename = parts
    return Shard(
        path=path,
        region=region,
        subregion=subregion,
        country=country,
        source=Path(filename).stem,
    )


def iter_shards(root: Optional[Path] = None) -> Iterator[Shard]:
    """Yield every shard under `root`, one per source. When a source has both a
    parquet and a CSV the parquet wins, so a half-migrated tree never yields the
    same source twice."""
    root = root or PER_SOURCE_DIR
    if not root.is_dir():
        return
    seen: set[str] = set()
    for suffix in SHARD_SUFFIXES:
        for path in sorted(root.rglob(f"*{suffix}")):
            shard = shard_from_path(path, root)
            if shard is None or shard.key in seen:
                continue
            seen.add(shard.key)
            yield shard


def _segment_regex(segment: str) -> str:
    out = []
    for ch in segment:
        if ch == "*":
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(ch))
    return "".join(out)


def compile_selector(selector: str) -> re.Pattern[str]:
    """Translate one selector into a regex over a shard key.

    `**` stands for any number of segments including none; `*` and `?` stay
    within one segment. A selector not already ending in `**` gets one appended,
    which is what makes a prefix select its whole subtree."""
    segments = [s for s in selector.strip("/").split("/") if s]
    if not segments:
        raise SelectorError("empty selector")
    if len(segments) > PARTITION_DEPTH and "**" not in segments:
        raise SelectorError(
            f"selector {selector!r} has more than {PARTITION_DEPTH} segments "
            f"({'/'.join(PARTITION_LEVELS)})"
        )
    if segments[-1] != "**":
        segments = segments + ["**"]

    parts: list[str] = []
    for i, segment in enumerate(segments):
        if segment == "**":
            parts.append("(?:[^/]+/)*" if i == 0 else "(?:/[^/]+)*")
        elif i == 0 or segments[i - 1] == "**":
            parts.append(_segment_regex(segment))
        else:
            parts.append("/" + _segment_regex(segment))
    return re.compile("^" + "".join(parts) + "$")


def selector_from_flags(
    region: Optional[str] = None,
    subregion: Optional[str] = None,
    country: Optional[str] = None,
) -> Optional[str]:
    """Turn the -r/-S/-c flags into one selector, filling skipped levels with
    `*`. Returns None when no flag was given, which means "everything"."""
    levels = [region, subregion, country]
    if not any(levels):
        return None
    filled = [level or "*" for level in levels]
    while filled and filled[-1] == "*":
        filled.pop()
    return "/".join(filled)


def select(
    selectors: Optional[Sequence[str]] = None,
    root: Optional[Path] = None,
    shards: Optional[Iterable[Shard]] = None,
) -> list[Shard]:
    """Every shard matching any of `selectors`, in stable key order. No
    selectors means every shard."""
    candidates = list(shards) if shards is not None else list(iter_shards(root))
    candidates.sort(key=lambda s: s.key)
    if not selectors:
        return candidates
    patterns = [compile_selector(s) for s in selectors]
    return [s for s in candidates if any(p.match(s.key) for p in patterns)]


def group_by(
    shards: Iterable[Shard], level: str
) -> "dict[tuple[str, ...], list[Shard]]":
    """Regroup shards onto a coarser level of the same tree, keyed by the path
    down to it. Free, because the levels are the shard's parent directories:
    `country` groups by (region, subregion, country).

    Stages want different axes — concatenate works per source, prepare per
    country — and this is what makes moving between them cost nothing."""
    if level not in PARTITION_LEVELS:
        raise SelectorError(
            f"unknown level {level!r}; expected one of {PARTITION_LEVELS}"
        )
    depth = PARTITION_LEVELS.index(level) + 1
    groups: dict[tuple[str, ...], list[Shard]] = {}
    for shard in sorted(shards, key=lambda s: s.key):
        key = tuple(shard.key.split("/")[:depth])
        groups.setdefault(key, []).append(shard)
    return groups


def order_longest_first(shards: Iterable[Shard]) -> list[Shard]:
    """Largest shard first — longest-processing-time-first scheduling. The
    shards are heavily skewed, so handing the biggest to the pool first keeps a
    late large shard from setting the wall clock on its own."""
    return sorted(shards, key=lambda s: (-s.size, s.key))


# Parquet-to-pandas expansion. Measured, not guessed: japan is 3.32 GB of shard
# and its prepare worker was OOM-killed at 13.3 GB anon RSS. These columns are
# mostly strings, which is where the factor comes from.
EXPANSION = 4


def memory_budget_bytes(fraction: float = 0.5) -> int:
    """Bytes of SHARD allowed in flight across a pool at once.

    Read from free memory rather than fixed, because the same number has to hold
    on an idle 26 GB box and on one already running a build. Divided by
    `EXPANSION` because the budget is denominated in on-disk bytes while the
    thing that overflows is resident memory.
    """
    import os  # noqa: PLC0415

    try:
        free = os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
    except (ValueError, AttributeError, OSError):
        free = 8 << 30
    return max(1 << 30, int(free * fraction) // EXPANSION)


def admits(inflight_bytes: int, n_inflight: int, next_size: int, budget: int) -> bool:
    """Whether the next unit of work may start now.

    An idle pool always admits. Without that, a unit larger than the whole
    budget is never admitted and the loop does not terminate — and japan, at
    3.32 GB against a 3 GB budget, is exactly that unit.
    """
    if n_inflight == 0:
        return True
    return inflight_bytes + next_size <= budget


def run_budgeted(jobs, fn, workers, budget, initializer=None) -> list:
    """Map `fn` over `jobs`, admitting work by BYTES in flight, not by count.

    `jobs` is an iterable of `(size_bytes, payload)`; `fn` is called with the
    payload. Results come back in completion order.

    A pool sized by cores is the version that OOMs on this corpus. The units are
    brutally skewed — japan is 3.32 GB against a median country in the low MB,
    and yahoo_shopping alone is 1.6 GB of that — so six workers is entirely safe
    for the median and fatal for the top one. Longest-first remains right for
    wall clock, but on its own it is precisely the order that starts the giants
    together.

    So size is a budget as well as a sort key. The pool then runs the small
    units wide and the large ones alone, and no one has to pick a worker count
    per corpus.
    """
    from concurrent.futures import (  # noqa: PLC0415
        FIRST_COMPLETED,
        ProcessPoolExecutor,
        wait,
    )

    pending = sorted(jobs, key=lambda j: -j[0])
    if workers <= 1 or len(pending) <= 1:
        return [fn(payload) for _, payload in pending]

    results, inflight = [], {}
    with ProcessPoolExecutor(max_workers=workers, initializer=initializer) as pool:
        while pending or inflight:
            while pending and len(inflight) < workers:
                if not admits(
                    sum(inflight.values()), len(inflight), pending[0][0], budget
                ):
                    break
                size, payload = pending.pop(0)
                inflight[pool.submit(fn, payload)] = size
            done, _ = wait(inflight, return_when=FIRST_COMPLETED)
            for fut in done:
                inflight.pop(fut)
                results.append(fut.result())
    return results
