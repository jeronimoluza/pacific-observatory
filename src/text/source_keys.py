"""Source keys of corpus folders (T23, TX-21).

The key of ``<country>/<folder>/news.csv`` is ``<country>_<folder without the
country name>``. Folders listed in ``configs/_aliases/source_aliases.yaml`` are
retired duplicates of another folder of the same country: their key resolves to
the winner folder's key and the build leaves them out even while they are still
on disk. Two remaining folders with one key stop the build.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

import yaml

ALIASES_FILE = Path(__file__).parent / "configs" / "_aliases" / "source_aliases.yaml"


class SourceKeyCollision(RuntimeError):
    pass


@cache
def aliases() -> dict[str, str]:
    """``<country>/<loser folder>`` -> winner folder."""
    return yaml.safe_load(ALIASES_FILE.read_text(encoding="utf-8")) or {}


def _folder_id(news_csv: Path) -> str:
    return f"{news_csv.parent.parent.name}/{news_csv.parent.name}"


def source_key(news_csv: Path) -> str:
    country = news_csv.parent.parent.name
    folder = aliases().get(_folder_id(news_csv), news_csv.parent.name)
    return f"{country}_{folder.replace(country, '').strip('_')}"


def active_news_files(paths: list[Path]) -> list[Path]:
    """Drop retired folders; raise if two remaining folders give one key."""
    keep = [p for p in paths if _folder_id(p) not in aliases()]
    by_key: dict[str, list[Path]] = {}
    for p in keep:
        by_key.setdefault(source_key(p), []).append(p)
    clash = {k: v for k, v in by_key.items() if len(v) > 1}
    if clash:
        detail = "; ".join(
            f"{k}: " + ", ".join(str(p.parent) for p in v) for k, v in sorted(clash.items())
        )
        raise SourceKeyCollision(
            f"folders with one source key (list the loser in {ALIASES_FILE.name}): {detail}"
        )
    return keep
