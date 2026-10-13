"""Shared trends and source breaks in concept/group series.

Two questions, per country in a region (default SSA), on the monthly
``<item>_<measure>`` index series:

1. Common factor. How much of all groups' movement is one or a few shared
   factors (PCA on log levels, number of factors by Bai-Ng IC_p2)? Does the
   first factor track article volume or the number of active sources? Does a
   pair's level co-movement (default excess_rainfall / state_capacity)
   survive once the factors are removed? Significance against
   phase-randomised surrogates, which keep each series' spectrum.
2. Source breaks. Change points (optimal partitioning, Gaussian mean-shift
   cost, BIC-type penalty) in log articles, active sources and factor 1;
   factor breaks within +/-2 months of a source break are flagged.

Writes a PDF and CSVs to outputs/text/reports/concepts-exploration-pdfs/.

Run: python src/text/analysis/explorations/common_factor.py [--region ssa]
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

from lead_lag import (  # noqa: E402
    MEASURE_LABELS,
    OUT,
    REPORT_DIR,
    ROOT,
    country_dirs,
    eligible,
    load_series,
    table_page,
    text_page,
)

MAX_FACTORS = 8
SURROGATES = 500
BREAK_WINDOW = 2  # months between a factor break and a source break
MIN_SEG = 6  # shortest segment between change points, months
PAIR = ("excess_rainfall", "state_capacity")


# --------------------------------------------------------------------------- factors


def standardize(df: pd.DataFrame) -> pd.DataFrame:
    x = np.log1p(df.clip(lower=0).fillna(0))
    sd = x.std(ddof=0)
    x = x.loc[:, sd > 0]
    return (x - x.mean()) / x.std(ddof=0)


def bai_ng_k(X: np.ndarray, kmax: int = MAX_FACTORS) -> int:
    """Number of factors minimising Bai & Ng (2002) IC_p2."""
    T, N = X.shape
    u, s, vt = np.linalg.svd(X, full_matrices=False)
    total = (X**2).sum()
    best, best_ic = 0, np.log(total / (N * T))
    for k in range(1, min(kmax, len(s)) + 1):
        v = (total - (s[:k] ** 2).sum()) / (N * T)
        ic = np.log(v) + k * (N + T) / (N * T) * np.log(min(N, T))
        if ic < best_ic:
            best, best_ic = k, ic
    return best


def factors(Z: pd.DataFrame) -> dict:
    """PCA on standardized log levels: factors, explained shares, residuals."""
    X = Z.to_numpy()
    u, s, vt = np.linalg.svd(X, full_matrices=False)
    k = bai_ng_k(X)
    share = s**2 / (s**2).sum()
    F = u[:, : max(k, 1)] * s[: max(k, 1)]
    # Orient factor 1 so a rise means most groups rise.
    if vt[0].sum() < 0:
        F[:, 0] *= -1
        vt[0] *= -1
    resid = X - (u[:, :k] * s[:k]) @ vt[:k] if k else X
    return {
        "k": k,
        "share": share,
        "F": pd.DataFrame(F, index=Z.index),
        "loadings": pd.Series(vt[0], index=Z.columns),
        "resid": pd.DataFrame(resid, index=Z.index, columns=Z.columns),
    }


def phase_surrogates(x: np.ndarray, n: int, rng: np.random.Generator) -> np.ndarray:
    """Surrogates with the same power spectrum as x (random Fourier phases)."""
    f = np.fft.rfft(x - x.mean())
    phases = rng.uniform(0, 2 * np.pi, size=(n, len(f)))
    phases[:, 0] = 0
    if len(x) % 2 == 0:
        phases[:, -1] = 0
    return np.fft.irfft(np.abs(f) * np.exp(1j * phases), n=len(x))


def level_corr(
    x: pd.Series, y: pd.Series, rng: np.random.Generator
) -> tuple[float, float]:
    """Correlation of two level series and its surrogate p-value."""
    a, b = x.to_numpy(), y.to_numpy()
    r = np.corrcoef(a, b)[0, 1]
    sur = phase_surrogates(b, SURROGATES, rng)
    null = np.array([np.corrcoef(a, s)[0, 1] for s in sur])
    p = (1 + (np.abs(null) >= abs(r)).sum()) / (1 + SURROGATES)
    return float(r), float(p)


# --------------------------------------------------------------------------- breaks


def change_points(x: np.ndarray, min_seg: int = MIN_SEG) -> list[int]:
    """Optimal partitioning with a Gaussian mean-shift cost.

    Penalty 3 * sigma^2 * log(n), with sigma estimated robustly from first
    differences, so slow drift alone does not trigger breaks.
    """
    x = np.asarray(x, float)
    n = len(x)
    if n < 2 * min_seg:
        return []
    sigma = np.median(np.abs(np.diff(x) - np.median(np.diff(x)))) * 1.4826 / np.sqrt(2)
    if sigma == 0:
        sigma = x.std() or 1.0
    pen = 3 * sigma**2 * np.log(n)
    c1 = np.concatenate([[0], np.cumsum(x)])
    c2 = np.concatenate([[0], np.cumsum(x**2)])

    def cost(i, j):  # segment x[i:j]
        m = j - i
        s = c1[j] - c1[i]
        return (c2[j] - c2[i]) - s * s / m

    F = np.full(n + 1, np.inf)
    F[0] = -pen
    last = np.zeros(n + 1, int)
    for j in range(min_seg, n + 1):
        for i in range(0, j - min_seg + 1):
            if i != 0 and i < min_seg:
                continue
            v = F[i] + cost(i, j) + pen
            if v < F[j]:
                F[j], last[j] = v, i
    cps, j = [], n
    while j > 0:
        i = last[j]
        if i > 0:
            cps.append(i)
        j = i
    return sorted(cps)


def source_activity(cache_file: Path, months: pd.DatetimeIndex) -> pd.DataFrame:
    """Monthly total articles and active sources from the country cache."""
    c = pd.read_parquet(cache_file, columns=["source_key", "ym", "A_total"])
    d = pd.to_datetime(c["ym"].astype(str), format="mixed")
    c["month"] = d.dt.to_period("M").dt.to_timestamp()
    g = c.groupby(["month", "source_key"])["A_total"].sum().reset_index()
    out = pd.DataFrame(
        {
            "articles": g.groupby("month")["A_total"].sum(),
            "sources": g[g.A_total > 0].groupby("month")["source_key"].nunique(),
        }
    )
    return out.reindex(months).fillna(0)


# --------------------------------------------------------------------------- main


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--region", default="ssa")
    ap.add_argument("--measure", default="intensity", choices=list(MEASURE_LABELS))
    ap.add_argument(
        "--outputs",
        type=Path,
        default=OUT,
        help="outputs/text root to read (e.g. a frozen worktree's)",
    )
    ap.add_argument("--cache", type=Path, default=ROOT / "data" / "text" / "cache")
    args = ap.parse_args()

    import lead_lag

    lead_lag.OUT = args.outputs
    dirs = country_dirs(args.region)
    rng = np.random.default_rng(0)
    rows, pair_rows, breaks, f1s, acts = [], [], [], {}, {}
    chance = []  # per country: share of months within the window of a source break

    for name, cdir in dirs.items():
        raw = eligible(load_series(cdir, "groups", args.measure))
        if raw.shape[1] < 20:
            continue
        Z = standardize(raw)
        fac = factors(Z)
        F1 = fac["F"][0]
        cache_file = (
            args.cache / cdir.relative_to(args.outputs) / "source_counts.parquet"
        )
        act = source_activity(cache_file, Z.index) if cache_file.exists() else None
        r_art = r_src = np.nan
        if act is not None:
            r_art = np.corrcoef(F1, np.log1p(act.articles))[0, 1]
            r_src = np.corrcoef(F1, act.sources)[0, 1]

        # Residual-vs-residual correlations are not comparable here: with as
        # many groups as months the residuals are linearly dependent.
        C = np.corrcoef(Z.to_numpy().T)
        mean_abs = np.nanmean(np.abs(C[~np.eye(len(C), dtype=bool)]))

        rows.append(
            {
                "country": name,
                "groups": Z.shape[1],
                "k": fac["k"],
                "F1_share": fac["share"][0],
                "F1..k_share": fac["share"][: fac["k"]].sum(),
                "r(F1, log articles)": r_art,
                "r(F1, sources)": r_src,
                "mean|r| between groups": mean_abs,
            }
        )
        f1s[name] = F1
        acts[name] = act

        # Breaks.
        cps_f1 = change_points(F1.to_numpy())
        cps_src = []
        if act is not None:
            cps_src = sorted(
                set(change_points(np.log1p(act.articles.to_numpy())))
                | set(change_points(act.sources.to_numpy()))
            )
        covered = np.zeros(len(Z), bool)
        for j in cps_src:
            covered[max(0, j - BREAK_WINDOW) : j + BREAK_WINDOW + 1] = True
        chance.extend([covered.mean()] * len(cps_f1))
        for kind, cps in (("factor1", cps_f1), ("source", cps_src)):
            for i in cps:
                near = kind == "factor1" and any(
                    abs(i - j) <= BREAK_WINDOW for j in cps_src
                )
                breaks.append(
                    {
                        "country": name,
                        "kind": kind,
                        "month": Z.index[i],
                        "near_source_break": near,
                    }
                )

        # Pair, on concepts.
        craw = load_series(cdir, "concepts", args.measure)
        if all(c in craw for c in PAIR):
            craw = craw.reindex(Z.index)
            cz = np.log1p(craw[list(PAIR)].clip(lower=0).fillna(0))
            dense = (craw[list(PAIR)].fillna(0) > 0).mean()
            if (cz.std(ddof=0) > 0).all():
                cz = (cz - cz.mean()) / cz.std(ddof=0)
                r_raw, p_raw = level_corr(cz[PAIR[0]], cz[PAIR[1]], rng)
                F = fac["F"].iloc[:, : max(fac["k"], 1)].to_numpy()
                beta = np.linalg.lstsq(F, cz.to_numpy(), rcond=None)[0]
                res = pd.DataFrame(
                    cz.to_numpy() - F @ beta, index=cz.index, columns=cz.columns
                )
                r_res, p_res = level_corr(res[PAIR[0]], res[PAIR[1]], rng)
                pair_rows.append(
                    {
                        "country": name,
                        f"nonzero {PAIR[0]}": dense[PAIR[0]],
                        f"nonzero {PAIR[1]}": dense[PAIR[1]],
                        "r raw": r_raw,
                        "p raw": p_raw,
                        "r resid": r_res,
                        "p resid": p_res,
                    }
                )
        print(f"{name}: k={fac['k']} F1={fac['share'][0]:.0%} r(F1,art)={r_art:+.2f}")

    summary = pd.DataFrame(rows).sort_values("F1_share", ascending=False)
    pairs = pd.DataFrame(pair_rows)
    brk = pd.DataFrame(breaks)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stem = (
        REPORT_DIR
        / f"{date.today():%Y-%m-%d}-common-factor-{args.region}-{args.measure}"
    )
    summary.to_csv(f"{stem}.factors.csv", index=False)
    pairs.to_csv(f"{stem}.pair.csv", index=False)
    brk.to_csv(f"{stem}.breaks.csv", index=False)

    n = len(summary)
    dense_pairs = (
        pairs[(pairs.iloc[:, 1] >= 0.8) & (pairs.iloc[:, 2] >= 0.8)]
        if len(pairs)
        else pairs
    )
    f1b = brk[brk.kind == "factor1"] if len(brk) else brk
    with PdfPages(f"{stem}.pdf") as pdf:
        text_page(
            pdf,
            f"Shared trends and source breaks: {args.region.upper()}",
            f"""Measure: {args.measure}  ("{MEASURE_LABELS[args.measure]}")
Data: monthly group index series, {n} countries with >= 20 dense groups (Mac)

METHOD
- Each group: log(1 + index), standardized. PCA across groups;
  number of factors k by Bai & Ng (2002) IC_p2 (max {MAX_FACTORS}).
- Factor 1 compared with log total articles and number of
  active sources per month (from the build cache).
- Pair test: {PAIR[0]} vs {PAIR[1]} level correlation, before
  and after regressing out the k factors. p-value against {SURROGATES}
  phase-randomised surrogates (same spectrum, random timing).
- Change points in log articles, active sources and factor 1:
  optimal partitioning, mean-shift cost, penalty 3 sigma^2 log n,
  segments >= {MIN_SEG} months. A factor-1 break within +/-{BREAK_WINDOW} months
  of a source break is flagged as source-driven.

RESULTS
Median k:                                {summary.k.median():.0f}
Median factor-1 share of variance:       {summary.F1_share.median():.0%}
Median share explained by k factors:     {summary["F1..k_share"].median():.0%}
Median r(factor 1, log articles):        {summary["r(F1, log articles)"].median():+.2f}
Median r(factor 1, active sources):      {summary["r(F1, sources)"].median():+.2f}
Median mean |r| between groups (levels): {summary["mean|r| between groups"].median():.2f}
  (independent noise of this length: about 0.07)

Pair {PAIR[0]} / {PAIR[1]}:
  countries tested:                      {len(pairs)}
  both series dense (>= 80% non-zero):   {len(dense_pairs)}
  raw level corr p < 0.05:               {int((pairs["p raw"] < 0.05).sum()) if len(pairs) else 0}
  after removing factors, p < 0.05:      {int((pairs["p resid"] < 0.05).sum()) if len(pairs) else 0}
  (chance alone: about {0.05 * len(pairs):.1f})

Breaks: {int((brk.kind == "source").sum()) if len(brk) else 0} source breaks, {len(f1b)} factor-1 breaks,
  of which {int(f1b.near_source_break.sum()) if len(f1b) else 0} ({f1b.near_source_break.mean() if len(f1b) else 0:.0%}) within +/-{BREAK_WINDOW} months of a source break;
  chance (share of months that close to a source break): {np.mean(chance) if chance else 0:.0%}.
""",
            size=8.5,
        )

        show = summary.copy()
        for c in show.columns[3:]:
            show[c] = show[c].map(lambda v: f"{v:.2f}")
        table_page(pdf, "Factors per country", show)

        # Factor 1 against article volume, 9 countries with the largest F1 share.
        top = summary.head(9).country.tolist()
        fig, axes = plt.subplots(3, 3, figsize=(11.69, 8.27), sharex=True)
        for ax, name in zip(axes.flat, top):
            F1 = f1s[name]
            ax.plot(
                F1.index,
                (F1 - F1.mean()) / F1.std(),
                color="#c0392b",
                lw=1,
                label="factor 1",
            )
            act = acts[name]
            if act is not None:
                la = np.log1p(act.articles)
                ax.plot(
                    la.index,
                    (la - la.mean()) / (la.std() or 1),
                    color="#2c3e50",
                    lw=1,
                    label="log articles",
                )
                s = act.sources
                ax.plot(
                    s.index,
                    (s - s.mean()) / (s.std() or 1),
                    color="#95a5a6",
                    lw=0.8,
                    ls="--",
                    label="active sources",
                )
            for _, b in (
                brk[(brk.country == name) & (brk.kind == "source")].iterrows()
                if len(brk)
                else []
            ):
                ax.axvline(b.month, color="#e67e22", lw=0.6)
            ax.set_title(name.replace("_", " "), fontsize=8, loc="left")
            ax.tick_params(labelsize=6)
        axes.flat[0].legend(fontsize=6)
        fig.suptitle(
            "Factor 1 vs article volume and active sources (z); orange = source breaks",
            fontsize=11,
        )
        fig.tight_layout(rect=(0, 0, 1, 0.95))
        pdf.savefig(fig)
        plt.close(fig)

        if len(pairs):
            pshow = pairs.copy()
            for c in pshow.columns[1:]:
                pshow[c] = pshow[c].map(lambda v: f"{v:.2f}")
            table_page(
                pdf,
                f"{PAIR[0]} vs {PAIR[1]}: level correlation before and after removing factors",
                pshow.sort_values("r raw", ascending=False),
                "p from phase-randomised surrogates. nonzero = share of months with any mention.",
            )

        if len(brk):
            fig, ax = plt.subplots(figsize=(11.69, 8.27))
            names = summary.country.tolist()
            for y, name in enumerate(names):
                b = brk[brk.country == name]
                s = b[b.kind == "source"]
                f = b[b.kind == "factor1"]
                ax.scatter(s.month, [y] * len(s), marker="|", s=120, color="#2c3e50")
                ax.scatter(
                    f.month,
                    [y] * len(f),
                    marker="o",
                    s=18,
                    color=np.where(f.near_source_break, "#e67e22", "#c0392b"),
                )
            ax.set_yticks(range(len(names)))
            ax.set_yticklabels([x.replace("_", " ") for x in names], fontsize=6)
            ax.set_title(
                "Change points: | source breaks, dots factor-1 breaks (orange = within +/-2 mo of a source break)",
                fontsize=10,
                loc="left",
            )
            fig.tight_layout()
            pdf.savefig(fig)
            plt.close(fig)
    print(f"wrote {stem}.pdf")


if __name__ == "__main__":
    main()
