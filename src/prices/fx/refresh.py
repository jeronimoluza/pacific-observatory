"""Fetch FX rates and write the cache. **The only module here that networks.**

Two entry points, one code path:

* :func:`rebuild` reproduces the whole history from scratch. The cache the
  corpus currently ships was a merge of at least two providers with no code on
  disk describing it, which is why a 22-day block of garbage MNT could sit in
  it undetected. After this, the cache is a function of the provider plus this
  file.
* :func:`refresh` extends an existing cache forward without refetching what is
  already there.

Both write through :func:`prices.fx.cache.save_cache`, which renames a temp
file into place, so a concurrent reader never sees a half-written CSV.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from prices.fx import frankfurter, pegs
from prices.fx.cache import (
    SOURCE_DERIVED_EUR_PEG,
    SOURCE_FRANKFURTER_V2,
    load_cache,
    merge_rows,
    save_cache,
)
from prices.fx.paths import FX_HISTORY_FLOOR, PRICES_FX_CACHE

logger = logging.getLogger(__name__)


def fetch_frame(
    currencies: list[str],
    start: str,
    end: str,
) -> pd.DataFrame:
    """Fetch ``currencies`` over ``[start, end]`` and apply the EUR pegs.

    Unknown codes are screened out before the request, because one bad code
    422s the whole batch. XPF is overwritten with its legally fixed peg
    against EUR rather than kept as fetched -- see :mod:`prices.fx.pegs`.
    """
    supported = frankfurter.supported_codes(scope_all=True)
    accepted, rejected = frankfurter.screen_quotes(currencies, supported)
    if rejected:
        logger.warning(
            "Not served by Frankfurter v2, skipped: %s", ", ".join(sorted(rejected))
        )

    # EUR is needed to derive the pegged currencies even if nobody asked for it.
    needs_eur = any(code in accepted for code in pegs.DERIVED_FROM_EUR)
    request = list(accepted)
    if needs_eur and "EUR" not in request:
        request.append("EUR")

    fetched = frankfurter.fetch_rates(request, start=start, end=end)
    fetched["source"] = SOURCE_FRANKFURTER_V2

    derive = tuple(c for c in pegs.DERIVED_FROM_EUR if c in accepted)
    if derive:
        eur = fetched[fetched["currency"] == "EUR"][["date", "rate_usd_to_local"]]
        derived = pegs.derive_eur_pegged(eur, codes=derive)
        derived["source"] = SOURCE_DERIVED_EUR_PEG
        # Drop the fetched (cross-derived, drifting) rows for these codes and
        # replace them wholesale with the peg.
        fetched = fetched[~fetched["currency"].isin(derive)]
        fetched = pd.concat([fetched, derived], ignore_index=True)
        logger.info("Derived %s rows for %s from the EUR peg", len(derived), derive)

    if needs_eur and "EUR" not in accepted:
        fetched = fetched[fetched["currency"] != "EUR"]

    return fetched.sort_values(["currency", "date"]).reset_index(drop=True)


def rebuild(
    out_path: Path,
    currencies: list[str] | None = None,
    start: str = FX_HISTORY_FLOOR,
    end: str | None = None,
    like_cache: Path | None = None,
) -> pd.DataFrame:
    """Rebuild the whole cache from the provider and write it to ``out_path``.

    ``currencies`` defaults to whatever ``like_cache`` (default: the live
    cache) holds, so a rebuild targets the corpus's actual currency set rather
    than everything the provider offers.
    """
    end = end or pd.Timestamp.today().normalize().strftime("%Y-%m-%d")
    if currencies is None:
        source_cache = load_cache(Path(like_cache or PRICES_FX_CACHE))
        currencies = sorted(source_cache["currency"].dropna().unique())
    logger.info(
        "Rebuilding %s currencies over %s..%s", len(currencies), start, end
    )
    frame = fetch_frame(currencies, start=start, end=end)
    written = save_cache(frame, out_path)
    logger.info("Wrote %s rows to %s", written, out_path)
    return frame


def refresh(
    cache_path: Path = PRICES_FX_CACHE,
    currencies: list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
) -> int:
    """Extend ``cache_path`` forward, preserving rows already present.

    With no ``start``, resumes from the day after the cache's last date.
    Returns the number of rows fetched.
    """
    cache_path = Path(cache_path)
    existing = load_cache(cache_path)
    if currencies is None:
        currencies = sorted(existing["currency"].dropna().unique())
    if start is None:
        if existing.empty:
            start = FX_HISTORY_FLOOR
        else:
            start = (existing["date"].max() + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    end = end or pd.Timestamp.today().normalize().strftime("%Y-%m-%d")

    if pd.Timestamp(start) > pd.Timestamp(end):
        logger.info("FX cache already current through %s", end)
        return 0

    fetched = fetch_frame(currencies, start=start, end=end)
    combined = merge_rows(existing, fetched)
    save_cache(combined, cache_path)
    logger.info("Refreshed %s rows into %s", len(fetched), cache_path)
    return int(len(fetched))
