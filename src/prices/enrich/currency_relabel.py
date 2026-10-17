"""Relabel a source's rows whose currency label is wrong over a date range.

A manifest's `relabel_currency: [{from, to, before | since}]` says that rows
labelled `from` and dated before (or on/after) a day carry `to` numbers. Applied
in `concatenate` after the modal back-fill, so the shard holds the right
label and the raw scrape on disk is never edited.

Bulgaria: four shops declare EUR, so the Common Crawl fetcher stamped EUR on
their pre-2026 pages, which priced in BGN (same URL and year, median ratio
1.0 against the BGN-labelled rows, ~1.95 against the live EUR price).
"""

from __future__ import annotations

import logging
from functools import lru_cache

import pandas as pd

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def rules() -> dict[tuple[str, str], list[dict]]:
    """`{(country, source): [rule, ...]}` for manifests that set `relabel_currency`."""
    from prices.config import PriceSourceConfig, discover_prices_configs

    out = {}
    for path in discover_prices_configs():
        try:
            cfg = PriceSourceConfig.load(path)
        except Exception:  # noqa: BLE001 - unloadable manifest
            continue
        if cfg.relabel_currency:
            out[(cfg.country, cfg.source)] = cfg.relabel_currency
    return out


def apply(df: pd.DataFrame, rules_: list[dict], scope: str = "") -> pd.DataFrame:
    """`df` with each rule's `from` rows in its date range relabelled `to`."""
    from prices.enrich.stages.prepare import parse_dates

    when = parse_dates(df["date"])
    label = df["currency"].astype(str).str.strip().str.upper()
    for r in rules_:
        hit = label.eq(str(r["from"]).upper())
        if "before" in r:
            hit &= when < pd.Timestamp(str(r["before"]), tz="UTC")
        if "since" in r:
            hit &= when >= pd.Timestamp(str(r["since"]), tz="UTC")
        if hit.any():
            df.loc[hit, "currency"] = str(r["to"]).upper()
            logger.info(
                "[currency_relabel] %s: %d %s rows relabelled %s",
                scope, int(hit.sum()), r["from"], r["to"],
            )
    return df
