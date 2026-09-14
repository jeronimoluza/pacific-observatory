"""Currencies that must be DERIVED from EUR rather than fetched.

Frankfurter has no Pacific issuing authority for the CFP franc, so it
cross-derives XPF through third-country tables and drifts +/-0.4% off a rate
French law fixes exactly. For a legally fixed peg the fetched number is not
merely noisier than the peg -- it is wrong, because the peg is the definition.

XPF: 1 EUR = 119.332 XPF, fixed since the 1999 euro changeover
(French monetary code; the pre-1999 FRF peg converts to the same value).
Affects 502,602 products across New Caledonia and French Polynesia.

XOF and XAF are also EUR-pegged, at 655.957 exactly, but Frankfurter already
holds them to that peg, so they are recorded here for documentation and
verified by test rather than overridden. PGK and SBD share XPF's
no-issuing-authority gap but are not pegged, so there is nothing to derive --
their rates stay as fetched. They are small (4,608 products combined).
"""

from __future__ import annotations

import pandas as pd

#: ISO code -> units of that currency per 1 EUR, fixed by law.
EUR_PEGS: dict[str, float] = {
    "XPF": 119.332,
    "XOF": 655.957,
    "XAF": 655.957,
}

#: Pegs we actually override the provider on. XOF/XAF match the provider
#: already, so overriding them would add churn without adding correctness.
DERIVED_FROM_EUR: tuple[str, ...] = ("XPF",)


def derive_eur_pegged(
    eur_rates: pd.DataFrame, codes: tuple[str, ...] = DERIVED_FROM_EUR
) -> pd.DataFrame:
    """Compute pegged rates from the EUR series.

    ``eur_rates`` is ``date, rate_usd_to_local`` for EUR (EUR per USD).
    Returns ``currency, date, rate_usd_to_local`` with

        rate_usd_to_<peg> = peg_per_eur * eur_per_usd

    so XPF per USD = 119.332 * EUR per USD.
    """
    if eur_rates.empty:
        return pd.DataFrame(columns=["currency", "date", "rate_usd_to_local"])
    base = eur_rates[["date", "rate_usd_to_local"]].dropna()
    frames = []
    for code in codes:
        peg = EUR_PEGS[code]
        frame = base.copy()
        frame["currency"] = code
        frame["rate_usd_to_local"] = peg * base["rate_usd_to_local"].to_numpy()
        frames.append(frame[["currency", "date", "rate_usd_to_local"]])
    if not frames:
        return pd.DataFrame(columns=["currency", "date", "rate_usd_to_local"])
    return pd.concat(frames, ignore_index=True)
