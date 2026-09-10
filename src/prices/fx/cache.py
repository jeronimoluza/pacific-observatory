"""On-disk FX cache: schema, load, save.

Schema is ``currency,date,rate_usd_to_local,source``.

``rate_usd_to_local`` is units of local currency per 1 USD, so
``price_usd = price_local / rate_usd_to_local``.

``source`` is the provenance marker. It exists because one class of row is
COMPUTED rather than fetched (see :mod:`prices.fx.pegs`), and a cache that
cannot tell you which is which cannot be audited. Values are
``<provider>:<api-version>`` for fetched rows and ``derived:<rule>`` for
computed ones -- see :data:`SOURCE_FRANKFURTER_V2` and friends. Rows loaded
from a pre-provenance cache get :data:`SOURCE_LEGACY`, which is the honest
answer: the old cache was a merge of at least two providers and nothing on
disk records which one wrote a given row.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

FX_COLUMNS = ["currency", "date", "rate_usd_to_local", "source"]

#: Fetched from api.frankfurter.dev/v2 (/v2/rates).
SOURCE_FRANKFURTER_V2 = "frankfurter:v2"
#: Computed from EUR at a legally fixed peg rather than fetched.
SOURCE_DERIVED_EUR_PEG = "derived:eur-peg"
#: Carried over from the pre-provenance cache; the writing provider is unknown.
SOURCE_LEGACY = "legacy:unknown"


def load_cache(cache_path: Path) -> pd.DataFrame:
    """Read the FX cache, tolerating a missing file and a missing ``source``.

    Returns a frame with :data:`FX_COLUMNS`, ``date`` normalised to midnight
    and ``rate_usd_to_local`` numeric. Rows with no currency or no parseable
    date are dropped.
    """
    cache_path = Path(cache_path)
    if not cache_path.exists():
        return pd.DataFrame(columns=FX_COLUMNS)
    try:
        cache = pd.read_csv(cache_path, low_memory=False)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=FX_COLUMNS)

    for col in ("currency", "date", "rate_usd_to_local"):
        if col not in cache.columns:
            cache[col] = None
    if "source" not in cache.columns:
        # A cache written before provenance existed. Do not guess a provider.
        cache["source"] = SOURCE_LEGACY
    cache["source"] = cache["source"].fillna(SOURCE_LEGACY)

    cache["date"] = pd.to_datetime(cache["date"], errors="coerce").dt.normalize()
    cache["rate_usd_to_local"] = pd.to_numeric(
        cache["rate_usd_to_local"], errors="coerce"
    )
    cache = cache.dropna(subset=["currency", "date"])
    return cache[FX_COLUMNS].copy()


def save_cache(frame: pd.DataFrame, cache_path: Path) -> int:
    """Write ``frame`` to ``cache_path`` atomically, sorted and de-duplicated.

    The write goes to a sibling temp file and is then renamed, so a reader --
    or a second writer -- never observes a half-written CSV. That is the fix
    for the interleaved-rewrite corruption the fuel pipeline hits when several
    regions build in parallel against one stale cache.
    """
    cache_path = Path(cache_path)
    out = frame.copy()
    for col in FX_COLUMNS:
        if col not in out.columns:
            out[col] = SOURCE_LEGACY if col == "source" else None
    out = out[FX_COLUMNS]
    out = out.dropna(subset=["currency", "date"])
    out = out.drop_duplicates(subset=["currency", "date"], keep="last")
    out = out.sort_values(["currency", "date"]).reset_index(drop=True)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache_path.with_suffix(cache_path.suffix + ".tmp")
    out.to_csv(tmp, index=False)
    tmp.replace(cache_path)
    return int(len(out))


def merge_rows(existing: pd.DataFrame, fetched: pd.DataFrame) -> pd.DataFrame:
    """Upsert ``fetched`` over ``existing`` on ``(currency, date)``.

    Fetched rows go last so ``keep="last"`` lets fresh values win, while
    ``(currency, date)`` pairs that were not re-fetched are preserved.
    """
    frames = [f for f in (existing, fetched) if f is not None and not f.empty]
    if not frames:
        return pd.DataFrame(columns=FX_COLUMNS)
    combined = pd.concat(frames, ignore_index=True)
    combined = combined.dropna(subset=["currency", "date"])
    combined = combined.drop_duplicates(subset=["currency", "date"], keep="last")
    return combined.sort_values(["currency", "date"]).reset_index(drop=True)


def coverage(cache: pd.DataFrame) -> pd.DataFrame:
    """Per-currency first date, last date, row count and source mix."""
    if cache.empty:
        return pd.DataFrame(columns=["currency", "start", "end", "rows", "sources"])
    grouped = cache.groupby("currency")
    out = pd.DataFrame(
        {
            "start": grouped["date"].min(),
            "end": grouped["date"].max(),
            "rows": grouped["date"].count(),
            "sources": grouped["source"].agg(lambda s: ",".join(sorted(set(s)))),
        }
    )
    return out.reset_index()
