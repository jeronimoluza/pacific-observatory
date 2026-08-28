"""The set of sources the Common Crawl backfill should visit, resolved live.

The first version of this runner read a hand-built TSV of 623 rows. That file
went stale the moment a manifest gained an ``archive_prefix``, and it pinned
absolute paths from the machine that generated it. Reading the manifests
directly means the worklist is always exactly "every scoped source", on any
machine, with no file to regenerate.

Order is stable (region, country, spider) rather than manifest-discovery order
so a run interrupted on one machine and resumed on another walks the same
sequence.
"""

from __future__ import annotations

from typing import List, NamedTuple


class Source(NamedTuple):
    region: str
    subregion: str
    country: str
    spider: str


def build_worklist() -> List[Source]:
    """Every spider whose manifest declares an ``archive_prefix``.

    ``archive_prefix`` alone gates eligibility: the fetcher falls back to
    generic JSON-LD/meta extraction when a spider has no bespoke parser, so
    "has a parser" is not a precondition for trying.
    """
    from prices.config import PriceSourceConfig, discover_prices_configs

    seen: set[str] = set()
    out: List[Source] = []
    for path in discover_prices_configs():
        try:
            cfg = PriceSourceConfig.load(path)
        except Exception:
            continue
        if not (cfg.spider and cfg.archive_prefix):
            continue
        if cfg.spider in seen:
            continue
        seen.add(cfg.spider)
        out.append(Source(cfg.region, cfg.subregion, cfg.country, cfg.spider))
    return sorted(out, key=lambda s: (s.region, s.country, s.spider))
