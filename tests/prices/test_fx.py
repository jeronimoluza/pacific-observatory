"""Hermetic tests for the prices-local FX pre-warm helper + latest-rate fallback.

No network calls (the shared fetcher is monkeypatched) and no writes to real
data/ (cache paths point at tmp_path).
"""

from __future__ import annotations

import pandas as pd
import pytest

from prices.build import fx, fx_fetch


def test_prewarm_upserts_additively(tmp_path, monkeypatch):
    cache_path = tmp_path / "fx_cache.csv"
    # Pre-seed an existing (currency, date) row that must be preserved.
    pd.DataFrame(
        {
            "currency": ["FJD"],
            "date": ["2024-05-01"],
            "rate_usd_to_local": [2.20],
        }
    ).to_csv(cache_path, index=False)

    def fake_fetch(start, end, currencies):
        return {"2025-01-10": {"NPR": 133.0, "AUD": 1.5}}

    monkeypatch.setattr(fx_fetch.forex, "fetch_fx_rates", fake_fetch)

    added = fx_fetch.prewarm_fx_cache(currencies=["NPR", "AUD"], cache_path=cache_path)
    assert added == 2

    out = pd.read_csv(cache_path)
    assert list(out.columns) == ["currency", "date", "rate_usd_to_local"]
    # No duplicate (currency, date) keys.
    assert not out.duplicated(subset=["currency", "date"]).any()

    keyed = {
        (r.currency, str(pd.Timestamp(r.date).date())): r.rate_usd_to_local
        for r in out.itertuples()
    }
    # Pre-existing row preserved.
    assert keyed[("FJD", "2024-05-01")] == pytest.approx(2.20)
    # Newly fetched rows added.
    assert keyed[("NPR", "2025-01-10")] == pytest.approx(133.0)
    assert keyed[("AUD", "2025-01-10")] == pytest.approx(1.5)


def test_prewarm_updates_existing_key(tmp_path, monkeypatch):
    cache_path = tmp_path / "fx_cache.csv"
    pd.DataFrame(
        {
            "currency": ["NPR"],
            "date": ["2025-01-10"],
            "rate_usd_to_local": [100.0],
        }
    ).to_csv(cache_path, index=False)

    monkeypatch.setattr(
        fx_fetch.forex,
        "fetch_fx_rates",
        lambda start, end, currencies: {"2025-01-10": {"NPR": 133.0}},
    )

    fx_fetch.prewarm_fx_cache(currencies=["NPR"], cache_path=cache_path)
    out = pd.read_csv(cache_path)
    assert not out.duplicated(subset=["currency", "date"]).any()
    # Fresh fetched value wins on collision.
    val = out.loc[out["currency"] == "NPR", "rate_usd_to_local"].iloc[0]
    assert val == pytest.approx(133.0)


def test_latest_rate_fallback_for_nat_date(tmp_path, monkeypatch):
    cache_path = tmp_path / "fx_cache.csv"
    pd.DataFrame(
        {
            "currency": ["FJD", "FJD"],
            "date": ["2024-05-01", "2024-05-02"],
            "rate_usd_to_local": [2.20, 2.25],
        }
    ).to_csv(cache_path, index=False)

    # Prove the FALLBACK path, not a live fetch: any fetch attempt raises.
    def no_network(*args, **kwargs):
        raise AssertionError("network fetch must not happen")

    monkeypatch.setattr("fuel.fx.fetch_fx_rates", no_network)

    df = pd.DataFrame(
        {
            "price_local": [10.0, 10.0],
            "currency": ["FJD", "FJ"],  # "FJ" must normalize to FJD
            "observation_date": [pd.NaT, pd.NaT],
        }
    )

    out = fx.attach_fx_and_usd(df, cache_path=cache_path)

    latest_rate = 2.25
    assert out["price_usd"].iloc[0] == pytest.approx(10.0 / latest_rate)
    # FJ normalized to FJD and converts identically.
    assert out["price_usd"].iloc[1] == pytest.approx(10.0 / latest_rate)
    assert out["currency"].tolist() == ["FJD", "FJD"]


def test_tz_aware_observation_date_matches_naive_cache(tmp_path, monkeypatch):
    """Raw scrape dates carry a UTC offset (tz-aware); the FX cache dates are
    tz-naive. The date-only join must not raise on the tz mismatch."""
    cache_path = tmp_path / "fx_cache.csv"
    pd.DataFrame(
        {
            "currency": ["FJD", "FJD"],
            "date": ["2024-05-01", "2024-05-02"],
            "rate_usd_to_local": [2.20, 2.25],
        }
    ).to_csv(cache_path, index=False)
    monkeypatch.setattr(
        "fuel.fx.fetch_fx_rates",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no network")),
    )

    df = pd.DataFrame(
        {
            "price_local": [10.0],
            "currency": ["FJD"],
            "observation_date": [pd.Timestamp("2024-05-02 21:10:09+00:00")],
        }
    )
    out = fx.attach_fx_and_usd(df, cache_path=cache_path)
    assert out["price_usd"].iloc[0] == pytest.approx(10.0 / 2.25)  # same-day rate


def test_fallback_leaves_uncached_currency_null(tmp_path, monkeypatch):
    cache_path = tmp_path / "fx_cache.csv"
    pd.DataFrame(
        {
            "currency": ["FJD"],
            "date": ["2024-05-02"],
            "rate_usd_to_local": [2.25],
        }
    ).to_csv(cache_path, index=False)

    monkeypatch.setattr(
        "fuel.fx.fetch_fx_rates",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no network")),
    )

    # PHP has no cached rate -> stays null.
    df = pd.DataFrame(
        {
            "price_local": [10.0],
            "currency": ["PHP"],
            "observation_date": [pd.NaT],
        }
    )
    out = fx.attach_fx_and_usd(df, cache_path=cache_path)
    assert pd.isna(out["price_usd"].iloc[0])
