"""Stage B currency: each product-month at its month's USD rate, repriced into
the country's local currency. Split out of `stage_b` to keep it under 500 lines."""

from __future__ import annotations

import pandas as pd

from prices.enrich.stages.prepare import month_of
from prices.fx import attach as fx


def month_rates(pm: pd.DataFrame, local: str) -> pd.DataFrame:
    """Mean rate and `fx_suspect` per (currency, month) over `pm`'s months.

    The month's rate is the mean of its daily USD->local rates, forward-filled
    by `build_fx_table`; the month is `fx_suspect` when any of those days' rate
    is implausible.
    """
    known = pm["month"].dropna()
    start = pd.to_datetime(known.min(), format="%Y-%m")
    end = pd.to_datetime(known.max(), format="%Y-%m") + pd.offsets.MonthEnd(0)
    currencies = sorted(set(pm["currency"].dropna()) | {local})
    days = pd.DataFrame(
        [(c, d) for c in currencies for d in (start, end)], columns=["currency", "observation_date"]
    )
    table = fx._mark_suspect_rates(fx.build_fx_table(days), fx.PRICES_FX_CACHE)
    table["fx_rate"] = pd.to_numeric(table["fx_rate"], errors="coerce")
    table["month"] = month_of(pd.to_datetime(table["observation_date"]))
    return table.groupby(["currency", "month"]).agg(
        fx_rate=("fx_rate", "mean"), fx_suspect=("fx_suspect", "any")
    )


def month_fx(pm: pd.DataFrame, local: str, rates: pd.DataFrame | None = None) -> pd.DataFrame:
    """Each product-month at its month's rate (`month_rates`), repriced into `local`.

    A month quoted in another currency is repriced via USD
    (livingcost quotes New Zealand in USD: banded as NZD it sat at ~0.6x every
    other shop, blended in, and was trusted). One with no rate is left as
    quoted and marked `fx_suspect`.
    """
    pm = pm.assign(currency=pm["currency"].map(fx.normalize_currency_safe))
    if rates is None:
        rates = month_rates(pm, local)

    def at(currency: pd.Series) -> tuple[pd.Series, pd.Series]:
        key = pd.MultiIndex.from_arrays([currency, pm["month"]])
        rate = pd.Series(rates["fx_rate"].reindex(key).to_numpy(), index=pm.index, dtype=float)
        bad = pd.Series(rates["fx_suspect"].reindex(key).to_numpy(), index=pm.index)
        usd = currency.eq("USD").to_numpy()
        rate[usd] = 1.0
        bad[usd] = False
        return rate, bad.fillna(False).astype(bool)

    own_rate, _ = at(pm["currency"])
    local_rate, local_bad = at(pd.Series(local, index=pm.index))
    foreign = pm["currency"].ne(local)
    ok = foreign & own_rate.gt(0) & local_rate.notna()
    stuck = foreign & ~ok
    price = pd.to_numeric(pm["price"], errors="coerce")
    pm = pm.copy()
    pm["currency_quoted"] = pm["currency"]
    pm["price_local"] = price.where(~ok, price / own_rate * local_rate)
    pm.loc[ok, "currency"] = local
    pm["fx_rate"] = local_rate.where(~stuck, own_rate)
    pm["fx_suspect"] = local_bad | stuck
    return pm
