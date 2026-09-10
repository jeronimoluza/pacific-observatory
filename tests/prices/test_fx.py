"""Hermetic tests for prices.fx.

Nothing here touches the network and nothing writes to real ``data/`` --
cache paths point at ``tmp_path``, and the provider client is either
monkeypatched or asserted never to be called.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from prices.build import fx as build_fx
from prices.fx import aliases, audit, cache as fx_cache, frankfurter, pegs
from prices.fx.attach import attach_fx_and_usd


def _write_cache(path, rows):
    pd.DataFrame(rows, columns=["currency", "date", "rate_usd_to_local"]).to_csv(
        path, index=False
    )
    return path


# ── the alias map ────────────────────────────────────────────────────────────

def test_alias_map_covers_both_historical_sources():
    """The committed EAP map and the uncommitted post-EAP additions are merged.

    KM and CFPF lived only in an untracked template-repo worktree; losing them
    silently mislabels Bosnian and CFP-franc rows.
    """
    assert aliases.normalize_currency("FJ") == "FJD"
    assert aliases.normalize_currency("K") == "PGK"
    assert aliases.normalize_currency("T") == "TOP"
    assert aliases.normalize_currency("VNT") == "VUV"
    assert aliases.normalize_currency("KM") == "BAM"
    assert aliases.normalize_currency("CFPF") == "XPF"


def test_normalize_currency_safe_passes_through_iso_and_junk():
    assert aliases.normalize_currency_safe("php") == "PHP"
    assert aliases.normalize_currency_safe("  FJ ") == "FJD"
    # Unknown codes upper-case and pass through rather than raising, so one bad
    # row cannot abort a build.
    assert aliases.normalize_currency_safe("zzz") == "ZZZ"
    assert aliases.normalize_currency_safe(None) is None
    with pytest.raises(KeyError):
        aliases.normalize_currency("ZZZ")


# ── the per-currency floor ───────────────────────────────────────────────────

def test_latest_rate_fill_is_floored_per_currency(tmp_path):
    """A row predating a currency's coverage must stay null, not convert at today's rate.

    VES is the motivating case: coverage starts after the redenomination, so
    pricing a pre-coverage bolivar at the latest rate is wrong by orders of
    magnitude. A null price_usd is recoverable; a plausible wrong one is not.
    """
    path = _write_cache(
        tmp_path / "fx.csv",
        [("VES", "2018-05-29", 60.0), ("VES", "2026-01-01", 100000.0)],
    )
    df = pd.DataFrame(
        {
            "price_local": [10.0, 10.0],
            "currency": ["VES", "VES"],
            # One before coverage starts, one inside it but on an uncached day.
            "observation_date": [pd.Timestamp("2017-06-01"), pd.Timestamp("2026-02-01")],
        }
    )
    out = attach_fx_and_usd(df, cache_path=path)
    assert pd.isna(out["price_usd"].iloc[0]), "pre-coverage row must not convert"
    assert out["price_usd"].iloc[1] == pytest.approx(10.0 / 100000.0)


def test_latest_rate_fill_leaves_nat_dates_null(tmp_path):
    """An undated row cannot be checked against the coverage window, so it stays null."""
    path = _write_cache(tmp_path / "fx.csv", [("FJD", "2024-05-01", 2.20)])
    df = pd.DataFrame(
        {"price_local": [10.0], "currency": ["FJD"], "observation_date": [pd.NaT]}
    )
    out = attach_fx_and_usd(df, cache_path=path)
    assert pd.isna(out["price_usd"].iloc[0])


def test_uncached_currency_stays_null(tmp_path):
    path = _write_cache(tmp_path / "fx.csv", [("FJD", "2024-05-02", 2.25)])
    df = pd.DataFrame(
        {
            "price_local": [10.0],
            "currency": ["PHP"],
            "observation_date": [pd.Timestamp("2024-05-02")],
        }
    )
    out = attach_fx_and_usd(df, cache_path=path)
    assert pd.isna(out["price_usd"].iloc[0])


# ── attach behaviour that must not drift ─────────────────────────────────────

def test_attach_normalizes_and_converts(tmp_path):
    path = _write_cache(
        tmp_path / "fx.csv", [("FJD", "2024-05-01", 2.20), ("FJD", "2024-05-02", 2.25)]
    )
    df = pd.DataFrame(
        {
            "price_local": [10.0, 10.0],
            "currency": ["FJD", "FJ"],
            "observation_date": [pd.Timestamp("2024-05-02")] * 2,
        }
    )
    out = attach_fx_and_usd(df, cache_path=path)
    assert out["currency"].tolist() == ["FJD", "FJD"]
    assert out["price_usd"].tolist() == pytest.approx([10.0 / 2.25] * 2)


def test_tz_aware_observation_date_matches_naive_cache(tmp_path):
    """Scrape dates are tz-aware; cache dates are not. The date-only join must not raise."""
    path = _write_cache(
        tmp_path / "fx.csv", [("FJD", "2024-05-01", 2.20), ("FJD", "2024-05-02", 2.25)]
    )
    df = pd.DataFrame(
        {
            "price_local": [10.0],
            "currency": ["FJD"],
            "observation_date": [pd.Timestamp("2024-05-02 21:10:09+00:00")],
        }
    )
    out = attach_fx_and_usd(df, cache_path=path)
    assert out["price_usd"].iloc[0] == pytest.approx(10.0 / 2.25)


def test_weekend_gap_uses_prior_rate_and_records_its_date(tmp_path):
    path = _write_cache(tmp_path / "fx.csv", [("FJD", "2024-05-03", 2.25)])
    df = pd.DataFrame(
        {
            "price_local": [10.0],
            "currency": ["FJD"],
            "observation_date": [pd.Timestamp("2024-05-05")],
        }
    )
    out = attach_fx_and_usd(df, cache_path=path)
    assert out["price_usd"].iloc[0] == pytest.approx(10.0 / 2.25)
    assert pd.Timestamp(out["fx_rate_date"].iloc[0]) == pd.Timestamp("2024-05-03")


def test_usd_rows_pass_through(tmp_path):
    path = _write_cache(tmp_path / "fx.csv", [("FJD", "2024-05-02", 2.25)])
    df = pd.DataFrame(
        {
            "price_local": [7.5],
            "currency": ["USD"],
            "observation_date": [pd.Timestamp("2024-05-02")],
        }
    )
    out = attach_fx_and_usd(df, cache_path=path)
    assert out["price_usd"].iloc[0] == pytest.approx(7.5)
    assert out["fx_rate"].iloc[0] == 1.0


def test_attach_never_networks(tmp_path, monkeypatch):
    """The build must not fetch. Any provider call here is a test failure."""
    def boom(*args, **kwargs):
        raise AssertionError("attach_fx_and_usd must not touch the network")

    monkeypatch.setattr(frankfurter, "_get", boom)
    monkeypatch.setattr(frankfurter, "fetch_rates", boom)

    path = _write_cache(tmp_path / "fx.csv", [("FJD", "2024-05-02", 2.25)])
    df = pd.DataFrame(
        {
            "price_local": [10.0],
            "currency": ["FJD"],
            # A date the cache does not cover -- the old fuel primitive would
            # have gone and fetched it.
            "observation_date": [pd.Timestamp("2025-11-11")],
        }
    )
    attach_fx_and_usd(df, cache_path=path)


def test_build_fx_shim_reexports_public_interface():
    """aggregate.py imports from prices.build.fx; that must keep working."""
    assert build_fx.attach_fx_and_usd is attach_fx_and_usd
    assert build_fx.PRICES_FX_CACHE.name == "fx_cache.csv"


# ── the XPF derivation ───────────────────────────────────────────────────────

def test_xpf_is_derived_from_the_legal_eur_peg():
    """XPF_per_USD = 119.332 * EUR_per_USD, exactly.

    Frankfurter has no Pacific issuing authority and cross-derives XPF through
    third-country tables, drifting up to 1.7% off a rate French law fixes.
    """
    eur = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
            "rate_usd_to_local": [0.90, 0.95],
        }
    )
    out = pegs.derive_eur_pegged(eur)
    assert out["currency"].unique().tolist() == ["XPF"]
    assert out["rate_usd_to_local"].tolist() == pytest.approx(
        [119.332 * 0.90, 119.332 * 0.95]
    )
    implied = out["rate_usd_to_local"] / eur["rate_usd_to_local"].to_numpy()
    assert implied.tolist() == pytest.approx([119.332, 119.332])


def test_xof_xaf_are_documented_but_not_overridden():
    """They hold 655.957 at the provider already, so overriding adds churn only."""
    assert pegs.EUR_PEGS["XOF"] == 655.957
    assert pegs.EUR_PEGS["XAF"] == 655.957
    assert "XOF" not in pegs.DERIVED_FROM_EUR
    assert "XAF" not in pegs.DERIVED_FROM_EUR


# ── the unknown-code screen ──────────────────────────────────────────────────

def test_screen_quotes_splits_known_from_unknown():
    """One unknown code 422s the WHOLE batch, so screening is not politeness."""
    supported = {"FJD", "PHP", "EUR"}
    accepted, rejected = frankfurter.screen_quotes(
        ["FJD", "php", "ZZZ", "T"], supported
    )
    assert accepted == ["FJD", "PHP"]
    assert rejected == ["ZZZ", "T"]


def test_fetch_rates_screens_nothing_it_was_not_given(monkeypatch):
    """fetch_rates drops the base and de-duplicates, and asks for what remains."""
    seen = {}

    def fake_get(path, params=None):
        seen["params"] = params
        return [{"date": "2024-01-01", "base": "USD", "quote": "FJD", "rate": 2.2}]

    monkeypatch.setattr(frankfurter, "_get", fake_get)
    out = frankfurter.fetch_rates(["FJD", "fjd", "USD"], "2024-01-01", "2024-01-01")
    assert seen["params"]["quotes"] == "FJD"
    assert out["currency"].tolist() == ["FJD"]


def test_http_422_is_not_retried(monkeypatch):
    """A 422 names a bad code; retrying cannot fix it and hides the message."""
    import urllib.error

    calls = []

    def raise_422(*args, **kwargs):
        calls.append(1)
        raise urllib.error.HTTPError(
            "u", 422, "Unprocessable", {}, __import__("io").BytesIO(b"invalid currency: ZZZ")
        )

    monkeypatch.setattr(frankfurter.urllib.request, "urlopen", raise_422)
    with pytest.raises(ValueError, match="invalid currency"):
        frankfurter._get("/rates", {"quotes": "ZZZ"})
    assert len(calls) == 1


# ── the contamination detector ───────────────────────────────────────────────

def _series(currency, dates, rates):
    return pd.DataFrame(
        {"currency": currency, "date": pd.to_datetime(dates), "rate_usd_to_local": rates}
    )


def test_detector_catches_a_step_and_return_block():
    """The MNT shape: stable, 22 days of garbage orders of magnitude off, back."""
    dates = pd.date_range("2025-01-01", periods=400, freq="D")
    rates = np.full(400, 3590.0)
    bad = slice(200, 222)
    rates[bad] = np.linspace(0.61, 0.84, 22)
    cache = _series("MNT", dates, rates)

    blocks = audit.find_contaminated_blocks(cache)
    assert len(blocks) == 1
    row = blocks.iloc[0]
    assert row.currency == "MNT"
    assert row.start == dates[200]
    assert row.end == dates[221]
    assert row.days == 22
    assert row.ratio > 1000


def test_detector_ignores_a_real_redenomination():
    """A currency that steps and STAYS is a devaluation, not contamination.

    This is the whole discriminator: a lifetime-median test fires on SDG, VES,
    ARS, LBP, BYN, ZWL, SYP, SSP, KPW and IRR, where the move is real.
    """
    dates = pd.date_range("2018-01-01", periods=400, freq="D")
    rates = np.concatenate([np.full(200, 60.0), np.full(200, 60000.0)])
    cache = _series("VES", dates, rates)
    assert audit.find_contaminated_blocks(cache).empty


def test_detector_ignores_ordinary_float_noise():
    rng = np.random.default_rng(0)
    dates = pd.date_range("2020-01-01", periods=400, freq="D")
    rates = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.004, 400)))
    cache = _series("PHP", dates, rates)
    assert audit.find_contaminated_blocks(cache).empty


def test_detector_needs_both_sides_so_edge_blocks_are_a_known_blind_spot():
    """Documented limitation, asserted so it cannot regress silently."""
    dates = pd.date_range("2025-01-01", periods=300, freq="D")
    rates = np.full(300, 3590.0)
    rates[-10:] = 0.6  # block runs to the end of the series: no "after" side
    cache = _series("MNT", dates, rates)
    assert audit.find_contaminated_blocks(cache).empty


def test_flag_rate_outliers_marks_every_row_of_a_bad_block():
    dates = pd.date_range("2025-01-01", periods=400, freq="D")
    rates = np.full(400, 3590.0)
    rates[200:222] = 0.7
    cache = _series("MNT", dates, rates)
    flags = audit.flag_rate_outliers(cache)
    assert int(flags.sum()) == 22
    assert set(cache.loc[flags, "date"]) == set(dates[200:222])


def test_suspect_rate_fails_qa_fx_at_build_time(tmp_path):
    """The gate MNT walked through: a present-but-implausible rate must fail.

    qa_fx only ever asked whether fx_rate was non-null, so 22 days of garbage
    published as trusted.
    """
    dates = pd.date_range("2025-01-01", periods=400, freq="D")
    rates = np.full(400, 3590.0)
    rates[200:222] = 0.7
    path = tmp_path / "fx.csv"
    _series("MNT", dates, rates).to_csv(path, index=False)

    df = pd.DataFrame(
        {
            "price_local": [2998.0, 2998.0],
            "currency": ["MNT", "MNT"],
            "observation_date": [dates[210], dates[10]],
        }
    )
    out = attach_fx_and_usd(df, cache_path=path)
    assert bool(out["fx_suspect"].iloc[0]) is True, "contaminated day must be marked"
    assert bool(out["fx_suspect"].iloc[1]) is False, "clean day must not be marked"

    # And the gate itself must now fail the contaminated row. Before this
    # change qa_fx was fx_rate.notna(), so both rows passed.
    from prices.build.qa import compute_qa

    gated = compute_qa(out)
    assert bool(gated["qa_fx"].iloc[0]) is False
    assert bool(gated["qa_fx"].iloc[1]) is True


# ── cache schema and provenance ──────────────────────────────────────────────

def test_cache_without_source_column_loads_as_legacy(tmp_path):
    """The shipped cache predates provenance; do not guess a provider for it."""
    path = _write_cache(tmp_path / "fx.csv", [("FJD", "2024-05-01", 2.20)])
    loaded = fx_cache.load_cache(path)
    assert list(loaded.columns) == fx_cache.FX_COLUMNS
    assert loaded["source"].unique().tolist() == [fx_cache.SOURCE_LEGACY]


def test_save_cache_is_atomic_and_deduplicated(tmp_path):
    """Parallel builds interleaved a full-file rewrite and corrupted the CSV."""
    path = tmp_path / "fx.csv"
    frame = pd.DataFrame(
        {
            "currency": ["FJD", "FJD", "AUD"],
            "date": pd.to_datetime(["2024-05-01", "2024-05-01", "2024-05-01"]),
            "rate_usd_to_local": [2.20, 2.25, 1.5],
            "source": [fx_cache.SOURCE_FRANKFURTER_V2] * 3,
        }
    )
    written = fx_cache.save_cache(frame, path)
    assert written == 2  # last write wins on the duplicate key
    assert not list(tmp_path.glob("*.tmp")), "temp file must be renamed away"
    out = fx_cache.load_cache(path)
    assert out.loc[out.currency == "FJD", "rate_usd_to_local"].iloc[0] == 2.25


def test_missing_cache_file_is_empty_not_an_error(tmp_path):
    loaded = fx_cache.load_cache(tmp_path / "nope.csv")
    assert loaded.empty
    assert list(loaded.columns) == fx_cache.FX_COLUMNS
