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


#: Codes the provider serves only from a cutover date: earlier dates are the
#: predecessor's rate, rescaled. MRU replaced MRO at 10:1 on 2018-01-01. SSP
#: replaced SDG at par in 2011-07, but v2 serves SSP only from 2013-01-21.
SUCCESSORS = {"MRU": ("MRO", 10.0, "2018-01-01"), "SSP": ("SDG", 1.0, "2013-01-21")}

#: Until Myanmar floated the kyat on 2012-04-01 the provider serves the
#: official peg (~6.4 per USD) against a market rate of 800-1,300, and prices
#: are quoted at market. Before the float MMK comes from the World Bank RTFX
#: panel instead: the monthly median of `c_exchange_rate_unofficial` across
#: Myanmar's ~300 markets, held for every day of its month.
MMK_FLOAT = "2012-04-01"
RTFX_CSV = Path.home() / "data/wb_rtdi/WLD_2023_RTFX_v01_M/WLD_RTFX_mkt_2026-08-24.csv"
SOURCE_RTFX_MMK = "wb_rtfx:unofficial-median"


def _daily(monthly: pd.Series) -> pd.DataFrame:
    days = pd.date_range(monthly.index.min(), monthly.index.max() + pd.offsets.MonthEnd(0))
    rate = monthly.reindex(days.to_period("M").to_timestamp()).to_numpy()
    return pd.DataFrame({"date": days, "rate_usd_to_local": rate})


def _mmk_market(start: str, rtfx_csv: Path = RTFX_CSV) -> pd.DataFrame:
    df = pd.read_csv(rtfx_csv, usecols=["ISO3", "DATES", "c_exchange_rate_unofficial"])
    df = df[df["ISO3"].eq("MMR")]
    monthly = df.groupby(pd.to_datetime(df["DATES"]))["c_exchange_rate_unofficial"].median()
    monthly = monthly[(monthly.index >= pd.Timestamp(start)) & (monthly.index < pd.Timestamp(MMK_FLOAT))]
    return _daily(monthly).assign(currency="MMK", source=SOURCE_RTFX_MMK)


def backfill(cache_path: Path = PRICES_FX_CACHE, start: str = FX_HISTORY_FLOOR) -> int:
    """Extend ``cache_path`` BACKWARD to ``start``. Add-only: a ``(currency,
    date)`` already cached is never touched. Returns the number of rows added.
    """
    cache_path = Path(cache_path)
    existing = load_cache(cache_path)
    first = existing.groupby("currency")["date"].min()
    plain = sorted(set(existing["currency"].dropna()) - set(SUCCESSORS))
    end = (first.min() - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    frames = [fetch_frame(plain, start=start, end=end)]
    for code, (old, ratio, cutover) in SUCCESSORS.items():
        last = (pd.Timestamp(cutover) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        prior = fetch_frame([old], start=start, end=last)
        prior["rate_usd_to_local"] = prior["rate_usd_to_local"] / ratio
        frames.append(prior.assign(currency=code, source=f"derived:{old}/{ratio:g}"))
    added = pd.concat(frames, ignore_index=True)
    added = added[~(added["currency"].eq("MMK") & (added["date"] < pd.Timestamp(MMK_FLOAT)))]
    added = pd.concat([added, _mmk_market(start)], ignore_index=True)
    # Existing rows go last so they win every overlap: a backfill never edits.
    combined = merge_rows(added, existing)
    save_cache(combined, cache_path)
    n = len(combined) - len(existing)
    logger.info("Backfilled %s rows into %s", n, cache_path)
    return n
