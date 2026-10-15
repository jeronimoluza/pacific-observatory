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
  - new article rows past tail     → tail-only annotate (handled separately by
                                     `tail_extension`)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd


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


# ── Tail extension ───────────────────────────────────────────────────


def tail_extension(
    news_csv: Path,
    params: SourceCountsParams | None,
    source_key: str,
) -> tuple[pd.Timestamp | None, int] | None:
    """Detect whether ``news.csv`` has rows newer than the cached tail.

    Returns
    -------
    (cutoff, n_new) :
        ``cutoff`` is the strict lower bound (rows with ``date > cutoff`` need
        annotating); ``n_new`` is the number of such rows.
        If there is no cached tail or the source has zero cached rows, returns
        ``(None, n_total)`` so the caller falls back to a full annotate.
    None :
        ``news.csv`` could not be read (caller treats as full re-annotate).
    """
    try:
        dates = pd.to_datetime(
            pd.read_csv(news_csv, usecols=["date"], encoding="utf-8")["date"],
            format="mixed",
            errors="coerce",
        ).dropna()
    except Exception:
        return None

    if params is None or source_key not in params.tails:
        return (None, int(len(dates)))

    last_iso = params.tails[source_key].get("last_date")
    if not last_iso:
        return (None, int(len(dates)))

    cutoff = pd.Timestamp(last_iso)
    new_rows = int((dates > cutoff).sum())
    return (cutoff, new_rows)
