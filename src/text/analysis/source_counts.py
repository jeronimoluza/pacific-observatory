"""I/O and invalidation for the per-country `source_counts.parquet` artifact.

`source_counts.parquet` rows are keyed by (source_key, ym) and hold per-source-
per-month annotation counts (A_total, E/P/U, kwsums, EU/PU/EP, plus per-topic
and per-actor counts, U∩category counts and unconditional category counts).
The sidecar
`source_counts.params.json` records the source set, per-language SHA-256
hashes of the keyword files, per-source tail metadata, and a schema version.

Invalidation rules — see `is_stale`:
  - schema_version mismatch       → full re-annotate
  - source set differs             → full re-annotate
  - any keyword hash differs       → full re-annotate
  - a month's row count moved      → re-annotate the source from that month
                                     and replace its cells (`first_stale_month`)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from src.text.analysis.news_rows import clean_chunks


SCHEMA_VERSION = 4

KEYWORD_FAMILIES = ("topics", "actors")

# Order-preserving column groups. `topic_*_count`, `topic_*_U_count`,
# `topic_*_A_count` and the `actor_*` equivalents are appended dynamically from
# the bundle.
BASE_COLUMNS = (
    "source_key",
    "ym",
    "A_total",
    "E_count",
    "P_count",
    "U_count",
    "E_kwsum",
    "P_kwsum",
    "U_kwsum",
    "EU_count",
    "PU_count",
    "EP_count",
    "EPU_count",
)


# ── Paths ────────────────────────────────────────────────────────────


def parquet_path(country_cache_dir: Path) -> Path:
    return country_cache_dir / "source_counts.parquet"


def params_path(country_cache_dir: Path) -> Path:
    return country_cache_dir / "source_counts.params.json"


# ── Hashes ───────────────────────────────────────────────────────────


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def keyword_hash_bundle(
    keywords_root: Path, languages: Iterable[str]
) -> dict[str, dict[str, str]]:
    """Return ``{keyword_file: {language: sha256}}`` covering every language used.

    Covers the flat ``epu.json`` plus every theme file of the ``topics`` and
    ``actors`` families, so adding or editing a single theme invalidates the
    cache. Falls back to ``en`` per file, mirroring the resolution rules in
    ``utils._resolve_theme_file``.
    """
    themed = {
        f"{family}/{path.stem}.json": family
        for family in KEYWORD_FAMILIES
        for path in sorted((keywords_root / "en" / family).glob("*.json"))
    }
    keys = ["epu.json", *sorted(themed)]
    out: dict[str, dict[str, str]] = {key: {} for key in keys}
    for lang in sorted(set(languages)):
        for key in keys:
            candidate = keywords_root / lang / key
            if not candidate.exists():
                candidate = keywords_root / "en" / key
            if candidate.exists():
                out[key][lang] = _sha256_file(candidate)
    return out


# ── Read / write ─────────────────────────────────────────────────────


@dataclass
class SourceCountsParams:
    schema_version: int
    source_set: list[str]
    keyword_hashes: dict[str, dict[str, str]]
    tails: dict[str, dict]  # source_key -> {"last_date": iso, "n_rows": int}

    def to_json(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "source_set": sorted(self.source_set),
            "keyword_hashes": self.keyword_hashes,
            "tails": self.tails,
        }

    @classmethod
    def from_json(cls, data: dict) -> "SourceCountsParams":
        return cls(
            schema_version=int(data.get("schema_version", 0)),
            source_set=list(data.get("source_set", [])),
            keyword_hashes=dict(data.get("keyword_hashes", {})),
            tails=dict(data.get("tails", {})),
        )


def read_source_counts(
    country_cache_dir: Path,
) -> tuple[pd.DataFrame | None, SourceCountsParams | None]:
    pq = parquet_path(country_cache_dir)
    pp = params_path(country_cache_dir)
    if not (pq.exists() and pp.exists()):
        return None, None
    df = pd.read_parquet(pq)
    params = SourceCountsParams.from_json(json.loads(pp.read_text(encoding="utf-8")))
    return df, params


def write_source_counts(
    country_cache_dir: Path,
    df: pd.DataFrame,
    params: SourceCountsParams,
) -> None:
    country_cache_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(parquet_path(country_cache_dir), index=False)
    params_path(country_cache_dir).write_text(
        json.dumps(params.to_json(), indent=2), encoding="utf-8"
    )


# ── Staleness predicate ──────────────────────────────────────────────


def is_stale(
    params: SourceCountsParams | None,
    current_source_set: Iterable[str],
    current_keyword_hashes: dict[str, dict[str, str]],
) -> tuple[bool, str | None]:
    """Return (stale, reason). reason is None when not stale."""
    if params is None:
        return True, "no cache"
    if params.schema_version != SCHEMA_VERSION:
        return True, f"schema_version {params.schema_version} != {SCHEMA_VERSION}"
    if sorted(params.source_set) != sorted(current_source_set):
        return True, "source set changed"
    if params.keyword_hashes != current_keyword_hashes:
        return True, "keyword files changed"
    return False, None


# ── Lateness window ──────────────────────────────────────────────────


def first_stale_month(
    news_csv: Path,
    cached_rows: pd.DataFrame,
    subset_start: pd.Timestamp | None,
    subset_end: pd.Timestamp | None,
) -> pd.Timestamp | None:
    """First month whose annotatable row count in ``news.csv`` differs from the cache.

    ``cached_rows`` are the source's cached cells. A month moves when rows land
    past the tail, when a merge brings in late rows dated at or before it, or
    when rows leave the file. Returns the start of the earliest such month, or
    ``None`` when every month matches or ``news.csv`` cannot be read.
    """
    file_counts = pd.Series(dtype="int64")
    try:
        for rows, *_ in clean_chunks(news_csv, subset_start, subset_end):
            months = rows["date"].dt.to_period("M").value_counts()
            file_counts = file_counts.add(months, fill_value=0)
    except Exception:
        return None
    cached = pd.Series(dtype="int64")
    if not cached_rows.empty:
        dates = pd.to_datetime(cached_rows["ym"].astype(str), format="mixed")
        cached = cached_rows["A_total"].groupby(dates.dt.to_period("M").values).sum()
    diff = file_counts.sub(cached, fill_value=0)
    stale = diff.index[diff != 0]
    return stale.min().to_timestamp() if len(stale) else None
