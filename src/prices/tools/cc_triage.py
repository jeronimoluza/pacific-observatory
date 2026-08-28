"""Turn one source's run stats into a verdict a human can act on.

623 sources produce 623 stat blocks, which nobody reads. The failure modes are
distinguishable from the counters alone, so classify them at write time and
let the operator read a short worklist instead.

The distinction that matters most is *where* a source lost its rows:

- ``no_extract`` means the page was fetched and its HTML recovered, and the
  parser then returned nothing. That is the parser's fault.
- ``queried == 0`` means Common Crawl has no record under the configured
  prefix at all. That is ``archive_prefix``'s fault, and no parser change
  will ever fix it.
- ``capped`` means the run was budget-bound, not broken; the source needs a
  longer leash, not a code change.

Conflating those three sends the operator to the wrong file.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

# The CLI prints "  <key><pad> <value>". A key exactly as wide as the pad
# leaves a single space, so a two-or-more-space split silently drops it --
# which is how ``indexes_failed`` (14 chars against a 14-wide pad) went
# missing from every summary. Match one-or-more instead.
_STAT_LINE = re.compile(r"^\s{2,}([a-z_]+)\s+(\d+)\s*$")

# A source with fewer attempts than this has too little evidence to call its
# parser weak; the ratio is noise at small n.
MIN_ATTEMPTS_FOR_YIELD = 200
WEAK_YIELD = 0.10
DEPTH_LOST_INDEXES = 5
FLAKY_FETCH_RATIO = 0.20

# Most severe first. The primary verdict is the first flag that applies, so
# ordering here is the operator's reading order.
_PRIORITY = [
    "CRASHED",
    "NO_MANIFEST",
    "NO_ARCHIVE",
    "PARSER_DEAD",
    "PARSER_WEAK",
    "DEPTH_LOST",
    "FETCH_FLAKY",
    "BUDGET_BOUND",
    "NOTHING_NEW",
    "OK",
]


def parse_stats(text: str) -> Dict[str, int]:
    """Pull the ``Run stats`` block out of a CLI transcript."""
    stats: Dict[str, int] = {}
    for line in text.splitlines():
        m = _STAT_LINE.match(line)
        if m:
            stats[m.group(1)] = int(m.group(2))
    return stats


def classify(status: str, stats: Dict[str, int]) -> Tuple[str, List[str]]:
    """Return ``(primary_verdict, all_flags)`` for one finished source."""
    flags: List[str] = []

    if status != "completed":
        flags.append("CRASHED")

    queried = stats.get("queried", 0)
    skipped = stats.get("skipped", 0)
    parsed = stats.get("parsed", 0)
    no_extract = stats.get("no_extract", 0)
    fetch_failed = stats.get("fetch_failed", 0)
    parse_failed = stats.get("parse_failed", 0)
    capped = stats.get("capped", 0)
    indexes_failed = stats.get("indexes_failed", 0)

    attempted = parsed + no_extract + fetch_failed + parse_failed

    if queried == 0:
        # Nothing under the prefix in any crawl -- an archive_prefix problem.
        flags.append("NO_ARCHIVE")
    elif attempted == 0 and skipped:
        flags.append("NOTHING_NEW")

    if parsed == 0 and no_extract > 0:
        flags.append("PARSER_DEAD")
    elif attempted >= MIN_ATTEMPTS_FOR_YIELD and parsed / attempted < WEAK_YIELD:
        flags.append("PARSER_WEAK")

    if indexes_failed >= DEPTH_LOST_INDEXES:
        flags.append("DEPTH_LOST")

    if attempted and fetch_failed / attempted > FLAKY_FETCH_RATIO:
        flags.append("FETCH_FLAKY")

    if capped > 0 and capped > parsed:
        flags.append("BUDGET_BOUND")

    if not flags:
        flags.append("OK")

    primary = min(flags, key=lambda f: _PRIORITY.index(f) if f in _PRIORITY else 99)
    return primary, flags


def yield_ratio(stats: Dict[str, int]) -> float:
    """Share of fetched pages that produced at least one row."""
    attempted = (
        stats.get("parsed", 0)
        + stats.get("no_extract", 0)
        + stats.get("fetch_failed", 0)
        + stats.get("parse_failed", 0)
    )
    if not attempted:
        return 0.0
    return stats.get("parsed", 0) / attempted


# A year with fewer attempts than this cannot distinguish a broken parser from
# a thin crawl.
MIN_ATTEMPTS_PER_YEAR = 40
# A year yielding less than this share of the best year's rate is a different
# page template, not variance.
CLIFF_RATIO = 0.25


def _year_of(index: str) -> str:
    """``CC-MAIN-2019-04`` -> ``2019``."""
    parts = index.split("-")
    return parts[2] if len(parts) > 2 and parts[2].isdigit() else ""


def yield_by_year(per_index: Dict[str, Dict[str, int]]) -> Dict[str, float]:
    """Collapse the per-crawl breakdown into one parse rate per year."""
    totals: Dict[str, List[int]] = {}
    for index, counts in per_index.items():
        year = _year_of(index)
        if not year:
            continue
        parsed = counts.get("parsed", 0)
        attempted = (
            parsed
            + counts.get("no_extract", 0)
            + counts.get("fetch_failed", 0)
            + counts.get("parse_failed", 0)
        )
        acc = totals.setdefault(year, [0, 0])
        acc[0] += parsed
        acc[1] += attempted
    return {
        year: parsed / attempted
        for year, (parsed, attempted) in totals.items()
        if attempted >= MIN_ATTEMPTS_PER_YEAR
    }


def date_cliff(per_index: Dict[str, Dict[str, int]]) -> Dict[str, object]:
    """Detect a parser that works in some years and not others.

    Returns ``{}`` when the rate is flat. A site redesign shows up here as a
    year whose parse rate collapses against the best year -- which the summed
    counters cannot show, because a parser that dies halfway through the
    period reads there as a uniformly mediocre one.
    """
    rates = yield_by_year(per_index)
    if len(rates) < 2:
        return {}
    best_year = max(rates, key=lambda y: rates[y])
    worst_year = min(rates, key=lambda y: rates[y])
    best, worst = rates[best_year], rates[worst_year]
    if best <= 0 or worst >= best * CLIFF_RATIO:
        return {}
    broken = sorted(y for y, r in rates.items() if r < best * CLIFF_RATIO)
    return {
        "best_year": best_year,
        "best_yield": round(best, 4),
        "worst_year": worst_year,
        "worst_yield": round(worst, 4),
        "broken_years": broken,
    }
