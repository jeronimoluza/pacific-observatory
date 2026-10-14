"""Baker, Bloom and Davis (2016) index construction.

- ``panel``: Baker averages a fixed set of newspapers. Ours is the sources
  that publish in at least ``PANEL_SHARE`` of the baseline weeks; the rest
  still count in article totals and burst detection, but not in the plain
  mean of standardized ratios.
- ``index``: the index at any frequency from a country's daily files. The
  build writes the weekly one (our adaptation; Baker is monthly), and its
  monthly run reproduces the published monthly series.
- ``combine`` / ``combine_outputs``: regions and subregions from their
  countries, as Baker's European EPU, not from pooled sources.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.text.analysis.baseline import baseline_mask

PANEL_SHARE = 0.5


def panel(
    sources_daily: pd.DataFrame, cutoff_start: str | None, cutoff_end: str | None
) -> set[str]:
    """Sources with articles in >= PANEL_SHARE of the baseline weeks (W-SUN)."""
    d = sources_daily[sources_daily.A_total > 0]
    dates = pd.to_datetime(d.date)
    d = d[baseline_mask(dates, cutoff_start, cutoff_end).to_numpy()]
    week = pd.to_datetime(d.date).dt.to_period("W-SUN")
    weeks = pd.period_range(
        pd.Timestamp(cutoff_start), pd.Timestamp(cutoff_end), freq="W-SUN"
    )
    share = week.groupby(d.source_key.astype(str).to_numpy()).nunique() / len(weeks)
    return set(share.index[share >= PANEL_SHARE])


def _period(dates: pd.Series, freq: str) -> pd.Series:
    """Week ending Sunday ("W") or first of the month ("M")."""
    if freq == "W":
        return dates + pd.to_timedelta((6 - dates.dt.dayofweek) % 7, unit="D")
    return dates.dt.to_period("M").dt.to_timestamp()


def index(
    sources_daily: pd.DataFrame,
    terms_daily: pd.DataFrame,
    panel: set[str],
    freq: str,
    cutoff_start: str,
    cutoff_end: str,
) -> pd.DataFrame:
    """Baker index (periods x terms, mean 100 over the baseline) from daily files.

    Per source i and period t: X = term articles / articles, sigma_i = std of X
    over the baseline periods with articles, Y = X / sigma_i. Z_t = mean of Y
    over the panel sources with articles in t (and a defined sigma); a period
    with none is NaN. Index = 100 * Z / mean(Z over the baseline). The monthly
    run reproduces the published ``<g>_intensity``.
    """
    s = sources_daily.assign(
        source_key=sources_daily.source_key.astype(str),
        period=_period(pd.to_datetime(sources_daily.date), freq),
    )
    A = s.groupby(["period", "source_key"]).A_total.sum().unstack(fill_value=0)
    A = A.reindex(
        pd.date_range(
            A.index.min(), A.index.max(), freq="W-SUN" if freq == "W" else "MS"
        ),
        fill_value=0,
    )
    t = terms_daily.assign(
        source_key=terms_daily.source_key.astype(str),
        term=terms_daily.term.astype(str),
        period=_period(pd.to_datetime(terms_daily.date), freq),
    )
    t = t[t.source_key.isin(panel)]
    t = t.groupby(["source_key", "period", "term"])["count"].sum().reset_index()
    t["a"] = (
        A.stack()
        .reindex(pd.MultiIndex.from_frame(t[["period", "source_key"]]))
        .to_numpy()
    )
    t = t[t.a > 0]
    if t.empty:  # no panel source (or none with articles)
        return pd.DataFrame(index=A.index, dtype=float)
    t["x"] = t["count"] / t["a"]

    # sigma over the baseline periods with articles; periods with no mention are x = 0.
    base = baseline_mask(A.index, cutoff_start, cutoff_end).to_numpy()
    n = (A[base] > 0).sum()
    b = t[baseline_mask(t.period, cutoff_start, cutoff_end).to_numpy()]
    m = b.groupby(["source_key", "term"]).x.agg(s1="sum", s2=lambda x: (x * x).sum())
    nn = n.reindex(m.index.get_level_values("source_key")).to_numpy()
    var = (m.s2 - m.s1**2 / nn) / (nn - 1)
    sigma = np.sqrt(var.where((nn > 1) & (var > 1e-24)))
    t = t.join(sigma.rename("sigma"), on=["source_key", "term"]).dropna(
        subset=["sigma"]
    )

    ysum = (
        t.assign(y=t.x / t.sigma)
        .pivot_table(
            index="period", columns="term", values="y", aggfunc="sum", fill_value=0
        )
        .reindex(A.index, fill_value=0)
    )
    has = sigma.unstack().notna().reindex(columns=ysum.columns, fill_value=False)
    present = (A.reindex(columns=has.index, fill_value=0) > 0).astype(float)
    npresent = present @ has.astype(float)
    Z = ysum / npresent.where(npresent > 0)
    mean = Z[base].mean()
    return 100 * Z / mean.where(mean > 0)


def combine(
    frames: list[pd.DataFrame], cutoff_start: str, cutoff_end: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Countries to one index, as Baker's European EPU (2016).

    Each country series is scaled to unit std over the baseline, then averaged
    across the countries with a value (dates x series). Returns the average
    (``Z``) and the index (100 x Z / its baseline mean).
    """
    scaled = []
    for f in frames:
        sd = f[baseline_mask(f.index, cutoff_start, cutoff_end).to_numpy()].std()
        scaled.append(f / sd.where(sd > 0))
    Z = pd.concat(scaled).groupby(level=0).mean()
    mean = Z[baseline_mask(Z.index, cutoff_start, cutoff_end).to_numpy()].mean()
    return Z, 100 * Z / mean.where(mean > 0)


# Index files of a unit; every column but these is an index (or, ending in
# "_z", the series that index was normalized from).
INDEX_FILES = (
    "epu/epu.csv",
    "epu/topics_epu.csv",
    "epu/actors_epu.csv",
    "epu/groups_epu.csv",
    "epu/concepts_epu.csv",
    "uncertainty_attribution/topics.csv",
    "uncertainty_attribution/actors.csv",
    "uncertainty_attribution/groups.csv",
    "uncertainty_attribution/concepts.csv",
)
NOT_INDEX = ("date", "ym", "news_total")


def _tail_start(unit_dir: Path) -> str | None:
    """First daily row ("YYYY-MM-DD" ym) of a unit's monthly output."""
    path = unit_dir / "epu" / "epu.csv"
    if not path.exists():
        return None
    ym = pd.read_csv(path, usecols=["ym"]).ym.astype(str)
    daily = ym[ym.str.count("-") == 2]
    return daily.iloc[0] if len(daily) else None


def combine_outputs(
    unit_dir: Path, country_dirs: list[Path], cutoff_start: str, cutoff_end: str
) -> list[Path]:
    """Rewrite an aggregate's index columns from its countries' outputs.

    The aggregate's own files (article totals, pooled counts) stay; each index
    column is replaced by ``combine`` over the countries' same column, and each
    ``_z`` column by the matching average. Also writes ``weekly/baker.parquet``.

    A country whose daily tail starts in another month than the aggregate's
    (built by an earlier run) would put a daily row against a monthly one on
    the same date, so it is left out of every file. Returns those countries.
    """
    tail = _tail_start(unit_dir)
    stale = [d for d in country_dirs if _tail_start(d) != tail]
    country_dirs = [d for d in country_dirs if d not in stale]
    for rel in INDEX_FILES:
        path = unit_dir / rel
        parts = [pd.read_csv(d / rel) for d in country_dirs if (d / rel).exists()]
        if not path.exists() or not parts:
            continue
        out = pd.read_csv(path)
        dates = pd.to_datetime(out.date)
        cols = [c for c in out.columns if c not in NOT_INDEX and not c.endswith("_z")]
        frames = [
            p.set_index(pd.to_datetime(p.date)).reindex(columns=cols) for p in parts
        ]
        Z, idx = combine(frames, cutoff_start, cutoff_end)
        out[cols] = idx.reindex(dates)[cols].to_numpy()
        z = [c for c in out.columns if c.endswith("_z") and c[:-2] in cols]
        out[z] = Z.reindex(dates)[[c[:-2] for c in z]].to_numpy()
        out.to_csv(path, index=False, encoding="utf-8")

    weekly = [
        pd.read_parquet(p)
        for d in country_dirs
        if (p := d / "weekly" / "baker.parquet").exists()
    ]
    if weekly:
        _, idx = combine(weekly, cutoff_start, cutoff_end)
        idx.index.name = "week"
        (unit_dir / "weekly").mkdir(parents=True, exist_ok=True)
        idx.to_parquet(unit_dir / "weekly" / "baker.parquet")
    return stale
