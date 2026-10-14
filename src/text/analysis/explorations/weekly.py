"""Weekly shared trends and pooled lead-lag, from the daily-history build.

Reads ``<country>/daily/pooled_daily.parquet`` and ``sources_daily.parquet``
(``text build --daily-history``) for every country in a region.

1. Masking. A source-day is suspect when it holds more than
   ``SPIKE_X`` times that source's median non-zero day and at least
   ``SPIKE_MIN`` articles (dumps, backfills). A country-day is dropped when
   suspect source-days make up more than ``MASK_SHARE`` of its articles.
2. Weekly shares. Monday-Sunday weeks; share = articles mentioning the group /
   all articles (the dashboard's "How much the topic is discussed").
   Weeks with fewer than ``MIN_WEEK`` articles are missing.
3. Shared trend. PCA on standardized log shares; factor 1 vs log weekly
   articles and active sources (as the monthly common_factor.py).
4. Pooled lead-lag. Per country: log share minus week-of-year mean, weekly
   change, AR prewhitening (lags 1-4 and 52), ranks; missing weeks set to 0.
   Cross-correlations at lags -12..12 weeks, Fisher-z, averaged over the
   countries where both groups are dense (weights n - 3). Each ordered pair is
   scored at its largest |pooled z| when that sits at a positive lag.
   p-values: the same pooled statistic on circularly shifted copies (each
   country's series shifted independently), then Benjamini-Hochberg 5%.
   Sign consistency = countries agreeing in sign at the pair's lag.

Writes a PDF and CSVs to outputs/text/reports/concepts-exploration-pdfs/.

Run: python src/text/analysis/explorations/weekly.py [--region ssa]
"""

from __future__ import annotations

import argparse
import json
from datetime import date

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

from common_factor import bai_ng_k  # noqa: E402
from lead_lag import (  # noqa: E402
    OUT,
    REPORT_DIR,
    bh_reject,
    emp_p,
    labels,
    pretty,
    table_page,
    text_page,
)

SPIKE_X = 10
SPIKE_MIN = 20
MASK_SHARE = 0.25
MIN_WEEK = 20
MIN_NONZERO = 0.6  # share of valid weeks with a mention
MIN_COUNTRIES = 10  # countries where both groups are dense
MAX_LAG = 12
AR_LAGS = [[], [1], [1, 2], [1, 2, 3, 4], [52], [1, 52], [1, 2, 52], [1, 2, 3, 4, 52]]
AR_OFFSET = 52
NULL_DRAWS = 20
FDR = 0.05
TOP_N = 20
EXAMPLE = ("excess_rainfall", "state_capacity")


# --------------------------------------------------------------------------- data


def masked_days(sources: pd.DataFrame) -> pd.Series:
    """Per day: share of the country's articles in suspect source-days."""
    med = sources[sources.A_total > 0].groupby("source_key").A_total.median()
    s = sources.assign(med=sources.source_key.map(med))
    suspect = (s.A_total > SPIKE_X * s.med) & (s.A_total >= SPIKE_MIN)
    day_total = s.groupby("date").A_total.sum()
    day_bad = s[suspect].groupby("date").A_total.sum()
    return (day_bad / day_total).reindex(day_total.index, fill_value=0)


def weekly(country_dir, prefix: str = "group_") -> dict:
    """Weekly article totals, active sources and per-group shares."""
    d = country_dir / "daily"
    pooled = pd.read_parquet(d / "pooled_daily.parquet")
    sources = pd.read_parquet(d / "sources_daily.parquet")
    bad = masked_days(sources)
    drop = bad[bad > MASK_SHARE].index
    pooled = pooled.drop(index=pooled.index.intersection(drop))
    cols = [
        c for c in pooled.columns if c.startswith(prefix) and c.endswith("_A_count")
    ]
    wk = pooled[["A_total", *cols]].resample("W-SUN").sum()
    src = sources[~sources.date.isin(drop) & (sources.A_total > 0)]
    active = src.set_index("date").groupby("source_key").A_total.resample("W-SUN").sum()
    active = (active > 0).groupby(level="date").sum().reindex(wk.index, fill_value=0)
    valid = wk.A_total >= MIN_WEEK
    shares = wk[cols].div(wk.A_total.where(valid), axis=0)
    shares.columns = [c[len(prefix) : -len("_A_count")] for c in cols]
    return {
        "articles": wk.A_total.where(valid),
        "sources": active.where(valid),
        "shares": shares,
        "counts": wk[cols].set_axis(shares.columns, axis=1),
        "masked_days": len(drop),
    }


def dense(w: dict) -> pd.DataFrame:
    sh = w["shares"]
    ok = sh.notna().any(axis=1)
    frac = (sh[ok].fillna(0) > 0).mean()
    return sh.loc[:, frac >= MIN_NONZERO]


def log_share(w: dict, items) -> pd.DataFrame:
    """log((G + 0.5) / (A + 1)) from the first to the last valid week."""
    A = w["articles"]
    span = slice(A.first_valid_index(), A.last_valid_index())
    G = w["counts"][items].loc[span]
    return np.log((G + 0.5).div(A.loc[span] + 1, axis=0))


# --------------------------------------------------------------------------- prewhiten


def ar_resid(x: np.ndarray) -> np.ndarray:
    y = x[AR_OFFSET:]
    n = len(y)
    best, best_aic = y - y.mean(), np.inf
    for lags in AR_LAGS:
        X = np.column_stack(
            [np.ones(n)] + [x[AR_OFFSET - k : len(x) - k] for k in lags]
        )
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        r = y - X @ beta
        aic = n * np.log(r.var() + 1e-300) + 2 * (len(lags) + 1)
        if aic < best_aic:
            best, best_aic = r, aic
    return best


def prewhiten(L: pd.DataFrame) -> pd.DataFrame:
    """Week-of-year means out, weekly change, AR residuals, ranks. NaN weeks -> 0."""
    woy = L.index.isocalendar().week.clip(upper=52).to_numpy()
    L = L - L.groupby(woy).transform("mean")
    D = L.diff().iloc[1:]
    miss = D.isna()
    D = D.fillna(0)
    out = {}
    for c in D.columns:
        r = ar_resid(D[c].to_numpy())
        r[miss[c].to_numpy()[AR_OFFSET:]] = 0
        if r.std() > 0:
            rk = pd.Series(r).rank().to_numpy()
            out[c] = (rk - rk.mean()) / rk.std()
    return pd.DataFrame(out, index=D.index[AR_OFFSET:])


def lag_stack(R: np.ndarray) -> np.ndarray:
    n, k = R.shape
    M = np.empty((2 * MAX_LAG + 1, k, k))
    M[MAX_LAG] = R.T @ R / n
    for lag in range(1, MAX_LAG + 1):
        C = R[:-lag].T @ R[lag:] / (n - lag)
        M[MAX_LAG + lag] = C
        M[MAX_LAG - lag] = C.T
    return M


def shift(R: np.ndarray, rng) -> np.ndarray:
    n = len(R)
    return np.column_stack(
        [
            np.roll(R[:, j], rng.integers(2 * MAX_LAG, n - 2 * MAX_LAG))
            for j in range(R.shape[1])
        ]
    )


# --------------------------------------------------------------------------- pooling


class Pool:
    """Weighted mean Fisher-z over countries, aligned to one item list."""

    def __init__(self, items: list[str]):
        self.items = items
        self.pos = {c: i for i, c in enumerate(items)}
        k = len(items)
        self.zsum = np.zeros((2 * MAX_LAG + 1, k, k))
        self.wsum = np.zeros((k, k))
        self.pos_n = np.zeros((2 * MAX_LAG + 1, k, k), np.int16)
        self.n = np.zeros((k, k), np.int16)

    def add(self, cols: list[str], M: np.ndarray, n: int):
        idx = np.array([self.pos[c] for c in cols])
        ix = np.ix_(idx, idx)
        w = n - 3
        z = np.arctanh(np.clip(M, -0.999, 0.999))
        self.zsum[:, ix[0], ix[1]] += w * z
        self.wsum[ix] += w
        self.pos_n[:, ix[0], ix[1]] += (M > 0).astype(np.int16)
        self.n[ix] += 1

    def mean_z(self) -> np.ndarray:
        with np.errstate(invalid="ignore", divide="ignore"):
            return self.zsum / self.wsum

    def peaks(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """(i, j, lag, z) for ordered pairs peaking at a positive lag."""
        Z = np.nan_to_num(self.mean_z())
        peak = np.abs(Z).argmax(axis=0)
        lag = peak - MAX_LAG
        ok = (
            (lag > 0) & (self.n >= MIN_COUNTRIES) & ~np.eye(len(self.items), dtype=bool)
        )
        i, j = np.nonzero(ok)
        return i, j, lag[i, j], Z[peak[i, j], i, j]


def null_peaks(prew: dict[str, pd.DataFrame], items, draws: int) -> np.ndarray:
    rng = np.random.default_rng(7)
    out = []
    for _ in range(draws):
        pool = Pool(items)
        for R in prew.values():
            pool.add(list(R.columns), lag_stack(shift(R.to_numpy(), rng)), len(R))
        out.append(np.abs(pool.peaks()[3]))
    return np.concatenate(out)


# --------------------------------------------------------------------------- report


def factor_summary(name: str, w: dict) -> dict | None:
    sh = dense(w)
    if sh.shape[1] < 20:
        return None
    L = log_share(w, list(sh.columns))
    valid = w["articles"].notna()
    L = L[valid.reindex(L.index, fill_value=False)]
    Z = ((L - L.mean()) / L.std(ddof=0)).dropna(axis=1)
    X = Z.to_numpy()
    u, s, vt = np.linalg.svd(X, full_matrices=False)
    F1 = u[:, 0] * s[0] * (1 if vt[0].sum() >= 0 else -1)
    k = bai_ng_k(X)
    la = np.log(w["articles"][valid])
    return {
        "country": name,
        "weeks": len(Z),
        "groups": Z.shape[1],
        "k": k,
        "F1_share": (s[0] ** 2) / (s**2).sum(),
        "r(F1, log articles)": np.corrcoef(F1, la)[0, 1],
        "r(F1, sources)": np.corrcoef(F1, w["sources"][valid])[0, 1],
        "masked_days": w["masked_days"],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--region", default="ssa")
    ap.add_argument("--draws", type=int, default=NULL_DRAWS)
    args = ap.parse_args()

    schema = json.loads((OUT / "dashboard_data" / "keywords_schema.json").read_text())
    names = labels(schema)
    countries = {
        p.parents[1].name: p.parents[1]
        for p in sorted((OUT / args.region).glob("*/*/daily/pooled_daily.parquet"))
    }
    print(f"{len(countries)} countries with daily history")

    weeklies, prew, facs = {}, {}, []
    for name, cdir in countries.items():
        w = weekly(cdir)
        weeklies[name] = w
        f = factor_summary(name, w)
        if f:
            facs.append(f)
        sh = dense(w)
        if sh.shape[1] >= 2 and w["articles"].notna().sum() > AR_OFFSET + 52:
            prew[name] = prewhiten(log_share(w, list(sh.columns)))
    facs = pd.DataFrame(facs)
    print(
        f"factors: median F1 {facs.F1_share.median():.0%}, "
        f"r(F1, log articles) {facs['r(F1, log articles)'].median():+.2f}"
    )

    items = sorted(set().union(*[set(R.columns) for R in prew.values()]))
    pool = Pool(items)
    for R in prew.values():
        pool.add(list(R.columns), lag_stack(R.to_numpy()), len(R))
    i, j, lag, z = pool.peaks()
    null = null_peaks(prew, items, args.draws)
    p = emp_p(np.abs(z), null)
    pairs = pd.DataFrame(
        {
            "leader": [items[a] for a in i],
            "follower": [items[b] for b in j],
            "lag_weeks": lag,
            "pooled_r": np.tanh(z),
            "same_week_r": np.tanh(np.nan_to_num(pool.mean_z()[MAX_LAG, i, j])),
            "countries": pool.n[i, j],
            "agree": np.where(
                z > 0,
                pool.pos_n[MAX_LAG + lag, i, j],
                pool.n[i, j] - pool.pos_n[MAX_LAG + lag, i, j],
            ),
            "p": p,
        }
    )
    pairs["fdr"] = bh_reject(pairs.p.to_numpy(), FDR)
    pairs = pairs.sort_values("p").reset_index(drop=True)

    # Placebo: the whole pooled scan on one set of shifted copies.
    rng = np.random.default_rng(99)
    placebo = Pool(items)
    for R in prew.values():
        placebo.add(list(R.columns), lag_stack(shift(R.to_numpy(), rng)), len(R))
    pz = placebo.peaks()[3]
    placebo_pass = int(bh_reject(emp_p(np.abs(pz), null), FDR).sum())
    print(
        f"pooled: {len(items)} groups, {len(pairs):,} lead pairs, "
        f"{int(pairs.fdr.sum())} pass FDR (placebo {placebo_pass})"
    )

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stem = REPORT_DIR / f"{date.today():%Y-%m-%d}-weekly-{args.region}"
    pairs.to_csv(f"{stem}.pairs.csv", index=False)
    facs.to_csv(f"{stem}.factors.csv", index=False)

    top = pairs[pairs.fdr].head(TOP_N)
    shown = top if len(top) else pairs.head(10)
    with PdfPages(f"{stem}.pdf") as pdf:
        text_page(
            pdf,
            f"Weekly patterns: {args.region.upper()}",
            f"""Data: daily-history build, {len(countries)} countries (Mac), Monday-Sunday weeks.
Measure: share of articles mentioning each group ("How much the
topic is discussed"), pooled over sources.

MASKING
Source-days above {SPIKE_X}x the source's median day (and >= {SPIKE_MIN} articles) are
suspect; country-days where they are > {MASK_SHARE:.0%} of articles are dropped.
Masked country-days: {int(facs.masked_days.sum())} in total, median {facs.masked_days.median():.0f} per country.

SHARED TREND (weekly)
Median factor-1 share of variance:   {facs.F1_share.median():.0%}
Median k (Bai-Ng):                   {facs.k.median():.0f}
Median r(factor 1, log articles):    {facs["r(F1, log articles)"].median():+.2f}
Median r(factor 1, active sources):  {facs["r(F1, sources)"].median():+.2f}

POOLED LEAD-LAG (lags 1-{MAX_LAG} weeks)
Method: per country, log share minus week-of-year mean, weekly
change, AR prewhitening (lags 1-4, 52), ranks. Fisher-z averaged
over countries where both groups are dense (>= {MIN_NONZERO:.0%} of weeks
non-zero, >= {MIN_COUNTRIES} countries). p from {args.draws} sets of circularly
shifted copies; Benjamini-Hochberg {FDR:.0%}.
Countries in the scan:               {len(prew)}
Groups:                              {len(items)}
Ordered lead pairs tested:           {len(pairs):,}
Pass FDR:                            {int(pairs.fdr.sum())}
Same scan on shifted copies:         {placebo_pass}

agree = countries whose own correlation has the pooled sign at
the pair's lag, out of `countries`.
""",
            size=8.5,
        )

        show = shown.assign(
            leader=shown.leader.map(lambda x: pretty(x, names)),
            follower=shown.follower.map(lambda x: pretty(x, names)),
            pooled_r=shown.pooled_r.round(3),
            same_week_r=shown.same_week_r.round(3),
            p=shown.p.map(lambda v: f"{v:.2g}"),
        )
        table_page(
            pdf,
            "Top pooled lead pairs"
            if len(top)
            else "Strongest pooled candidates (none pass FDR)",
            show[
                [
                    "leader",
                    "follower",
                    "lag_weeks",
                    "pooled_r",
                    "same_week_r",
                    "countries",
                    "agree",
                    "p",
                    "fdr",
                ]
            ],
        )

        # Pooled CCF for the top pairs.
        Z = pool.mean_z()
        lags = np.arange(-MAX_LAG, MAX_LAG + 1)
        crit = np.tanh(np.quantile(null, 0.95))
        k = min(len(shown), 12)
        if k:
            fig, axes = plt.subplots(4, 3, figsize=(11.69, 8.27), sharex=True)
            for ax, row in zip(axes.flat, shown.head(k).itertuples()):
                a, b = pool.pos[row.leader], pool.pos[row.follower]
                r = np.tanh(Z[:, a, b])
                ax.bar(lags, r, color=["#c0392b" if x > 0 else "#7f8c8d" for x in lags])
                ax.axhline(crit, color="#e67e22", ls="--", lw=0.7)
                ax.axhline(-crit, color="#e67e22", ls="--", lw=0.7)
                ax.set_title(
                    f"{pretty(row.leader, names)[:28]} -> {pretty(row.follower, names)[:28]}",
                    fontsize=7,
                    loc="left",
                )
                ax.tick_params(labelsize=6)
            for ax in list(axes.flat)[k:]:
                ax.axis("off")
            fig.suptitle(
                "Pooled cross-correlation by lag in weeks (red = leader first; dashed = 95th pct of shifted peaks)",
                fontsize=10,
            )
            fig.tight_layout(rect=(0, 0, 1, 0.95))
            pdf.savefig(fig)
            plt.close(fig)

        fshow = facs.sort_values("F1_share", ascending=False).copy()
        for c in ["F1_share", "r(F1, log articles)", "r(F1, sources)"]:
            fshow[c] = fshow[c].map(lambda v: f"{v:.2f}")
        table_page(pdf, "Weekly shared factor per country", fshow)

        # The worked example, on concepts, pooled.
        ex_rows = []
        for name, cdir in countries.items():
            w = weekly(cdir, prefix="concept_")
            if not all(c in w["shares"] for c in EXAMPLE):
                continue
            frac = (w["shares"][list(EXAMPLE)].dropna().fillna(0) > 0).mean()
            R = prewhiten(log_share(w, list(EXAMPLE)))
            if len(R.columns) < 2:
                continue
            M = lag_stack(R.to_numpy())
            ex_rows.append(
                {
                    "country": name,
                    "nonzero_a": frac.iloc[0],
                    "nonzero_b": frac.iloc[1],
                    "n": len(R),
                }
                | {
                    f"lag{lg:+d}": M[MAX_LAG + lg, 0, 1]
                    for lg in (-4, -2, -1, 0, 1, 2, 4, 8, 12)
                }
            )
        if ex_rows:
            ex = pd.DataFrame(ex_rows)
            wts = ex.n - 3
            pooled_row = {
                "country": "POOLED (weighted Fisher-z)",
                "nonzero_a": "",
                "nonzero_b": "",
                "n": int(ex.n.sum()),
            }
            for c in [c for c in ex.columns if c.startswith("lag")]:
                pooled_row[c] = np.tanh(
                    (np.arctanh(ex[c].clip(-0.999, 0.999)) * wts).sum() / wts.sum()
                )
            ex = pd.concat([ex, pd.DataFrame([pooled_row])], ignore_index=True)
            for c in ex.columns[1:]:
                ex[c] = ex[c].map(lambda v: f"{v:.2f}" if isinstance(v, float) else v)
            table_page(
                pdf,
                f"{EXAMPLE[0]} -> {EXAMPLE[1]}: weekly correlation by lag (positive = rainfall first)",
                ex,
                f"Prewhitened weekly changes. Shifted-copy 95% line for one pooled peak: about {crit:.3f}.",
            )
    print(f"wrote {stem}.pdf")


if __name__ == "__main__":
    main()
