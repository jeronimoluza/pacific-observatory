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


def _period(
    dates: pd.Series, freq: str, anchor: pd.Timestamp | None = None
) -> pd.Series:
    """Week ending Sunday ("W"), first of the month ("M"), or the last day of
    k-day blocks counted back from ``anchor`` ("<k>D"; later dates are NaT)."""
    if freq == "W":
        return dates + pd.to_timedelta((6 - dates.dt.dayofweek) % 7, unit="D")
    if freq.endswith("D"):
        k, back = int(freq[:-1]), (anchor - dates).dt.days
        return (anchor - pd.to_timedelta(back // k * k, unit="D")).where(back >= 0)
    return dates.dt.to_period("M").dt.to_timestamp()


def block_start(cutoff_start: str | None, freq: str) -> str | None:
    """The first "<k>D" block label inside a baseline starting at
    ``cutoff_start``: blocks are labelled by their last day, so a block lies
    in the baseline from k - 1 days after its start."""
    if cutoff_start is None:
        return None
    first = pd.Timestamp(cutoff_start) + pd.Timedelta(days=int(freq[:-1]) - 1)
    return f"{first:%Y-%m-%d}"


def _shares(
    sources_daily: pd.DataFrame,
    terms_daily: pd.DataFrame,
    panel: set[str],
    freq: str,
    anchor: pd.Timestamp | None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Articles per period and source (A), and per panel source, period and
    term with articles the term articles and their share (x)."""
    s = sources_daily.assign(
        source_key=sources_daily.source_key.astype(str),
        period=_period(pd.to_datetime(sources_daily.date), freq, anchor),
    )
    A = s.groupby(["period", "source_key"]).A_total.sum().unstack(fill_value=0)
    if freq.endswith("D"):
        periods = pd.date_range(end=anchor, start=A.index.min(), freq=freq)
    else:
        periods = pd.date_range(
            A.index.min(), A.index.max(), freq="W-SUN" if freq == "W" else "MS"
        )
    A = A.reindex(periods, fill_value=0)
    t = terms_daily.assign(
        source_key=terms_daily.source_key.astype(str),
        term=terms_daily.term.astype(str),
        period=_period(pd.to_datetime(terms_daily.date), freq, anchor),
    )
    t = t[t.source_key.isin(panel)]
    t = t.groupby(["source_key", "period", "term"])["count"].sum().reset_index()
    t["a"] = (
        A.stack()
        .reindex(pd.MultiIndex.from_frame(t[["period", "source_key"]]))
        .to_numpy()
    )
    t = t[t.a > 0]
    return A, t.assign(x=t["count"] / t["a"])


def _sigma(
    A: pd.DataFrame,
    t: pd.DataFrame,
    cutoff_start: str,
    cutoff_end: str,
    min_base_articles: int,
) -> pd.Series:
    """sigma_i per (source, term): std of x over the baseline periods with
    articles (periods with no mention are x = 0); NaN under the floor."""
    base = baseline_mask(A.index, cutoff_start, cutoff_end).to_numpy()
    n = (A[base] > 0).sum()
    b = t[baseline_mask(t.period, cutoff_start, cutoff_end).to_numpy()]
    m = b.groupby(["source_key", "term"]).x.agg(s1="sum", s2=lambda x: (x * x).sum())
    nn = n.reindex(m.index.get_level_values("source_key")).to_numpy()
    var = (m.s2 - m.s1**2 / nn) / (nn - 1)
    sigma = np.sqrt(var.where((nn > 1) & (var > 1e-24)))
    if min_base_articles:
        nb = b.groupby(["source_key", "term"])["count"].sum()
        sigma = sigma.where(nb.reindex(sigma.index) >= min_base_articles)
    return sigma


def _z(A: pd.DataFrame, t: pd.DataFrame, sigma: pd.Series) -> pd.DataFrame:
    """Z_t = mean of x / sigma_i over the sources with articles in t and a sigma."""
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
    return ysum / npresent.where(npresent > 0)


def index(
    sources_daily: pd.DataFrame,
    terms_daily: pd.DataFrame,
    panel: set[str],
    freq: str,
    cutoff_start: str,
    cutoff_end: str,
    min_base_articles: int = 0,
    anchor: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Baker index (periods x terms, mean 100 over the baseline) from daily files.

    Per source i and period t: X = term articles / articles, sigma_i = std of X
    over the baseline periods with articles, Y = X / sigma_i. Z_t = mean of Y
    over the panel sources with articles in t (and a defined sigma); a period
    with none is NaN. Index = 100 * Z / mean(Z over the baseline). The monthly
    run reproduces the published ``<g>_intensity``.

    ``min_base_articles``: a source enters a term only with at least that many
    term articles over the baseline (the panel rule, per term). A source that
    almost never covered a term has a sigma near 0, and its next few articles
    would dominate the mean.

    ``anchor``: the last day of the latest period at freq "<k>D" (periods are
    k-day blocks counted back from it, labelled by their last day). A block
    is in the baseline only when it lies entirely inside it (``block_start``).
    """
    if freq.endswith("D"):
        cutoff_start = block_start(cutoff_start, freq)
    A, t = _shares(sources_daily, terms_daily, panel, freq, anchor)
    if t.empty:  # no panel source (or none with articles)
        return pd.DataFrame(
            index=A.index, columns=pd.Index([], dtype=object), dtype=float
        )
    Z = _z(A, t, _sigma(A, t, cutoff_start, cutoff_end, min_base_articles))
    mean = Z[baseline_mask(A.index, cutoff_start, cutoff_end).to_numpy()].mean()
    return 100 * Z / mean.where(mean > 0)


def stepped(
    sources_daily: pd.DataFrame,
    terms_daily: pd.DataFrame,
    panel: set[str],
    freq: str,
    step: int,
    cutoff_start: str,
    cutoff_end: str,
    min_base_articles: int = 0,
    anchor: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The "<k>D" index (as ``index``) and the same k days moved back ``step``
    days at a time from ``anchor`` (a moving window), read with the blocks'
    sigma_i and mean 100: on a block's last day the two are the same value."""
    cutoff_start = block_start(cutoff_start, freq)
    A, t = _shares(sources_daily, terms_daily, panel, freq, anchor)
    if t.empty:  # no panel source (or none with articles)
        none = pd.DataFrame(index=A.index, columns=pd.Index([], dtype=object))
        return none.astype(float), none.astype(float)
    sigma = _sigma(A, t, cutoff_start, cutoff_end, min_base_articles)
    Z = _z(A, t, sigma)
    mean = Z[baseline_mask(A.index, cutoff_start, cutoff_end).to_numpy()].mean()
    mean = mean.where(mean > 0)
    parts = [100 * Z / mean]
    for back in range(step, int(freq[:-1]), step):
        At, tt = _shares(
            sources_daily,
            terms_daily,
            panel,
            freq,
            anchor - pd.Timedelta(days=back),
        )
        parts.append(100 * _z(At, tt, sigma).reindex(columns=Z.columns) / mean)
    return parts[0], pd.concat(parts).sort_index()


def monthly_family(
    sources_daily: pd.DataFrame,
    terms_daily: pd.DataFrame,
    panel: set[str],
    freqs: list[str],
    cutoff_start: str,
    cutoff_end: str,
    min_base_articles: int = 0,
    anchor: pd.Timestamp | None = None,
) -> dict[str, pd.DataFrame]:
    """The monthly Baker index ("M", as ``index``) and the same index at other
    frequencies: each source's sigma_i and the mean 100 are the monthly
    index's (calendar months over the baseline), so a week or a k-day block is
    the same standardized share read over another window, on the same scale
    (a k-day block is about the mean of its weeks)."""
    A, t = _shares(sources_daily, terms_daily, panel, "M", None)
    if t.empty:  # no panel source (or none with articles): no terms at any frequency
        none = pd.Index([], dtype=object)
        out = {"M": pd.DataFrame(index=A.index, columns=none, dtype=float)}
        for f in freqs:
            idx = _shares(sources_daily, terms_daily, panel, f, anchor)[0].index
            out[f] = pd.DataFrame(index=idx, columns=none, dtype=float)
        return out
    sigma = _sigma(A, t, cutoff_start, cutoff_end, min_base_articles)
    Z = _z(A, t, sigma)
    mean = Z[baseline_mask(A.index, cutoff_start, cutoff_end).to_numpy()].mean()
    mean = mean.where(mean > 0)
    out = {"M": 100 * Z / mean}
    for f in freqs:
        A, t = _shares(sources_daily, terms_daily, panel, f, anchor)
        out[f] = 100 * _z(A, t, sigma).reindex(columns=Z.columns) / mean
    return out


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


def combine_family(
    families: list[dict[str, pd.DataFrame]],
    cutoff_start: str,
    cutoff_end: str,
    ref: str = "M",
) -> dict[str, pd.DataFrame]:
    """``combine`` for ``monthly_family`` outputs: each country scaled by the
    std of its monthly index over the baseline at every frequency, averaged,
    and over the mean of the monthly average, so the frequencies stay on one
    scale. ``ref``: the family member read in place of the monthly index
    (``stepped``: the blocks)."""
    sds = [
        f[ref][baseline_mask(f[ref].index, cutoff_start, cutoff_end).to_numpy()].std()
        for f in families
    ]
    out = {}
    for k in families[0]:
        scaled = [f[k] / sd.where(sd > 0) for f, sd in zip(families, sds)]
        out[k] = pd.concat(scaled).groupby(level=0).mean()
    mean = out[ref][
        baseline_mask(out[ref].index, cutoff_start, cutoff_end).to_numpy()
    ].mean()
    return {k: 100 * Z / mean.where(mean > 0) for k, Z in out.items()}


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
