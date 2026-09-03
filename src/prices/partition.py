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


def order_longest_first(shards: Iterable[Shard]) -> list[Shard]:
    """Largest shard first — longest-processing-time-first scheduling. The
    shards are heavily skewed, so handing the biggest to the pool first keeps a
    late large shard from setting the wall clock on its own."""
    return sorted(shards, key=lambda s: (-s.size, s.key))
