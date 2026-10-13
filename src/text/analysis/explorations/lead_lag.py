"""Lead-lag exploration of concept and group series.

Asks whether talk about one group (or concept) systematically precedes talk
about another, e.g. excess rainfall -> state capacity in Argentina.

Method, per country, on the monthly ``<item>_<measure>`` index series:

1. Log, minus month-of-year means, monthly change.
2. Prewhiten each series with its own AR model (lags 1-3 and 12, by AIC).
3. Rank-transform, so single spike months do not dominate.
4. Cross-correlate every ordered pair at lags -6..6 months. A pair counts as
   "A leads B" when the largest absolute correlation sits at a positive lag.
5. p-values come from timing-scrambled copies (each series circularly
   shifted by its own random offset), then Benjamini-Hochberg at 5%.
   Textbook p-values were far too optimistic on this data.
6. Replication: the same pair, same sign, at the same lag +/-1, beating the
   95th percentile of that country's own scrambled copies, in at least 3
   other LAC countries.

Writes a PDF to outputs/text/reports/concepts-exploration-pdfs/.

Run: python src/text/analysis/explorations/lead_lag.py [--country argentina]
"""

from __future__ import annotations

import argparse
import json
import re
import textwrap
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from scipy import stats  # noqa: E402

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "outputs" / "text"
DATA = ROOT / "data" / "text"
REPORT_DIR = OUT / "reports" / "concepts-exploration-pdfs"

MAX_LAG = 6
AR_LAGSETS = [[], [1], [1, 2], [1, 2, 3], [12], [1, 12], [1, 2, 12], [1, 2, 3, 12]]
AR_OFFSET = 12
HOME_SHIFTS = 100  # circular-shift draws for the home country's null
OTHER_SHIFTS = 20  # per replication country
MIN_NONZERO = 0.8  # share of months with a non-zero value
FDR = 0.05
REP_ALPHA = 0.05
MIN_REPS = 3
TOP_N = 20
EXAMPLE_CONCEPTS = ("excess_rainfall", "state_capacity")
EXAMPLE_GROUPS = ("drought_rainfall", "government_administration")
MEASURE_LABELS = {
    "intensity": "How much the topic is discussed",
    "absolute": "How much uncertainty is about the topic",
    "framing": "The topic's share of uncertainty",
}
MONTHLY_YM = re.compile(r"^\d{4}-\d{1,2}$")


# --------------------------------------------------------------------------- data


def country_dirs(region: str) -> dict[str, Path]:
    """Country name -> output dir, for every country with attribution CSVs."""
    found = {}
    for p in sorted((OUT / region).glob("*/*/uncertainty_attribution/groups.csv")):
        country = p.parents[1]
        if country.name != "_aggregate":
            found[country.name] = country
    return found


def load_series(country_dir: Path, level: str, measure: str) -> pd.DataFrame:
    """Monthly ``<item>_<measure>`` columns, full months only, indexed by date."""
    path = country_dir / "uncertainty_attribution" / f"{level}.csv"
    suffix = f"_{measure}"
    head = pd.read_csv(path, nrows=0).columns
    cols = [c for c in head if c.endswith(suffix)]
    df = pd.read_csv(path, usecols=["date", "ym", *cols], dtype={"ym": str})
    df = df[df["ym"].str.match(MONTHLY_YM)]
    df.index = pd.to_datetime(df.pop("date"))
    df = df.drop(columns="ym")
    df.columns = [c[: -len(suffix)] for c in df.columns]
    return df.astype(float)


def eligible(df: pd.DataFrame, min_nonzero: float = MIN_NONZERO) -> pd.DataFrame:
    """Drop sparse series: too many zero or missing months."""
    share = (df.fillna(0) > 0).mean()
    return df.loc[:, share >= min_nonzero]


def ar_residuals(x: np.ndarray) -> np.ndarray:
    """Residuals of the AIC-best AR model over AR_LAGSETS, aligned to x[AR_OFFSET:]."""
    y = x[AR_OFFSET:]
    n = len(y)
    best, best_aic = y - y.mean(), np.inf
    for lags in AR_LAGSETS:
        X = np.column_stack(
            [np.ones(n)] + [x[AR_OFFSET - k : len(x) - k] for k in lags]
        )
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        resid = y - X @ beta
        aic = n * np.log(resid.var() + 1e-300) + 2 * (len(lags) + 1)
        if aic < best_aic:
            best, best_aic = resid, aic
    return best


def prewhiten(df: pd.DataFrame) -> pd.DataFrame:
    """Log, remove month-of-year means, first difference, AR prewhitening, ranks.

    Rows = months, cols = items. Ranks make single spike months (e.g. COVID)
    count no more than any other month.
    """
    lg = np.log1p(df.clip(lower=0).fillna(0))
    lg = lg - lg.groupby(lg.index.month).transform("mean")
    d = lg.diff().iloc[1:]
    out = {}
    for col in d.columns:
        r = ar_residuals(d[col].to_numpy())
        if r.std() > 0:
            rk = pd.Series(r).rank().to_numpy()
            out[col] = (rk - rk.mean()) / rk.std()
    return pd.DataFrame(out, index=d.index[AR_OFFSET:])


def circular_shift(R: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Roll each column by its own random offset: keeps each series, breaks timing."""
    n = len(R)
    return np.column_stack(
        [
            np.roll(R[:, j], rng.integers(MAX_LAG * 2, n - MAX_LAG * 2))
            for j in range(R.shape[1])
        ]
    )


def emp_p(obs: np.ndarray, null: np.ndarray) -> np.ndarray:
    """Share of null values >= each observed value, with the +1 correction."""
    null = np.sort(null)
    above = len(null) - np.searchsorted(null, obs, side="left")
    return (1 + above) / (1 + len(null))


def lag_stack(R: np.ndarray) -> np.ndarray:
    """M[MAX_LAG + l, i, j] = corr(i at t-l, j at t) for l in -MAX_LAG..MAX_LAG."""
    n, k = R.shape
    M = np.empty((2 * MAX_LAG + 1, k, k))
    M[MAX_LAG] = R.T @ R / n
    for lag in range(1, MAX_LAG + 1):
        C = R[:-lag].T @ R[lag:] / (n - lag)
        M[MAX_LAG + lag] = C
        M[MAX_LAG - lag] = C.T
    return M


def bh_reject(p: np.ndarray, q: float) -> np.ndarray:
    """Benjamini-Hochberg rejections at false-discovery rate q."""
    order = np.argsort(p)
    ranked = p[order] * len(p) / np.arange(1, len(p) + 1)
    passed = ranked <= q
    keep = np.zeros(len(p), bool)
    if passed.any():
        keep[order[: np.nonzero(passed)[0].max() + 1]] = True
    return keep


def group_ancestors(schema: dict) -> dict[str, set[str]]:
    """Group id -> ids of its ancestor groups (keyword sets overlap)."""
    parent = {}
    for heading in schema["headings"].values():
        for gid, g in heading["groups"].items():
            parent[gid] = g.get("parent")
    out = {}
    for gid in parent:
        seen, p = set(), parent[gid]
        while p and p not in seen:
            seen.add(p)
            p = parent.get(p)
        out[gid] = seen
    return out


def group_concepts(schema: dict) -> dict[str, list[str]]:
    """Group id -> concepts in the group and all of its descendant groups."""
    groups = {
        gid: g for h in schema["headings"].values() for gid, g in h["groups"].items()
    }

    def collect(gid, seen):
        if gid in seen or gid not in groups:
            return []
        seen.add(gid)
        out = list(groups[gid].get("concepts", []))
        for child in groups[gid].get("groups", []):
            out += collect(child, seen)
        return out

    return {gid: collect(gid, set()) for gid in groups}


def labels(schema: dict) -> dict[str, str]:
    out = {}
    for h in schema["headings"].values():
        for gid, g in h["groups"].items():
            out[gid] = g.get("label", gid)
    return out


def pretty(item: str, names: dict[str, str]) -> str:
    return names.get(item, item.replace("_", " ").capitalize())


# --------------------------------------------------------------------------- analysis


class Country:
    """Prewhitened series and their lag stack for one country and level."""

    def __init__(
        self,
        raw: pd.DataFrame,
        shifts: int = OTHER_SHIFTS,
        seed: int = 0,
        R: pd.DataFrame | None = None,
        min_nonzero: float = MIN_NONZERO,
    ):
        self.raw = raw
        self.R = prewhiten(eligible(raw, min_nonzero)) if R is None else R
        self.items = list(self.R.columns)
        self.pos = {c: i for i, c in enumerate(self.items)}
        self.n = len(self.R)
        self.M = lag_stack(self.R.to_numpy()) if self.items else None
        self.null_peaks, self.rep_threshold = self._null(shifts, seed)

    def _null(self, shifts: int, seed: int) -> tuple[np.ndarray, float]:
        """Null from circularly shifted copies of this country's own series.

        null_peaks: |r| of every positive-lag peak (what `scan` tests).
        rep_threshold: 95th percentile of the best same-sign r over a 3-lag
        window (what `replicates` tests).
        """
        if len(self.items) < 2:
            return np.array([1.0]), np.inf
        rng = np.random.default_rng(seed)
        k = len(self.items)
        shifts = min(5000, max(shifts, 20000 // (k * (k - 1))))
        peaks, windows = [], []
        off = ~np.eye(len(self.items), dtype=bool)
        for _ in range(shifts):
            M = lag_stack(circular_shift(self.R.to_numpy(), rng))
            idx = np.abs(M).argmax(axis=0)
            mask = (idx > MAX_LAG) & off
            peaks.append(np.abs(np.take_along_axis(M, idx[None], 0)[0][mask]))
            windows.append(M[MAX_LAG + 2 : MAX_LAG + 5].max(axis=0)[off])
        return np.concatenate(peaks), float(
            np.quantile(np.concatenate(windows), 1 - REP_ALPHA)
        )

    def ccf(self, a: str, b: str) -> np.ndarray | None:
        if a not in self.pos or b not in self.pos:
            return None
        return self.M[:, self.pos[a], self.pos[b]]

    def peak_p(self, r: float) -> float:
        return float(emp_p(np.array([abs(r)]), self.null_peaks)[0])


def scan(home: Country, exclude: set[tuple[str, str]] = frozenset()) -> pd.DataFrame:
    """Every ordered pair whose peak correlation sits at a positive lag."""
    M = home.M
    k = len(home.items)
    peak = np.abs(M).argmax(axis=0)
    lag = peak - MAX_LAG
    ii, jj = np.nonzero((lag > 0) & ~np.eye(k, dtype=bool))
    r = M[peak[ii, jj], ii, jj]
    p = emp_p(np.abs(r), home.null_peaks)
    df = pd.DataFrame(
        {
            "leader": [home.items[i] for i in ii],
            "follower": [home.items[j] for j in jj],
            "lag": lag[ii, jj],
            "r": r,
            "r0": M[MAX_LAG, ii, jj],
            "p": p,
        }
    )
    if exclude:
        drop = [(a, b) in exclude for a, b in zip(df.leader, df.follower)]
        df = df[~np.array(drop, bool)].reset_index(drop=True)
    df["fdr"] = bh_reject(df["p"].to_numpy(), FDR)
    return df


def replicates(
    pairs: pd.DataFrame, others: dict[str, Country]
) -> tuple[np.ndarray, pd.DataFrame]:
    """Count other countries where a pair repeats (same sign, lag +/-1).

    Returns the counts and a pairs x countries frame of the best same-sign r
    (NaN where either series is ineligible there).
    """
    rvals = pd.DataFrame(np.nan, index=pairs.index, columns=list(others))
    hits = np.zeros(len(pairs), int)
    tested = np.zeros(len(pairs), int)
    for name, c in others.items():
        if not c.items:
            continue
        ia = pairs.leader.map(c.pos)
        ib = pairs.follower.map(c.pos)
        ok = ia.notna() & ib.notna()
        if not ok.any():
            continue
        idx = np.nonzero(ok.to_numpy())[0]
        a = ia[ok].astype(int).to_numpy()
        b = ib[ok].astype(int).to_numpy()
        lag = pairs.lag.to_numpy()[idx]
        sign = np.sign(pairs.r.to_numpy()[idx])
        best = np.full(len(idx), np.nan)
        sig = np.zeros(len(idx), bool)
        for d in (-1, 0, 1):
            ll = lag + d
            valid = (ll >= 1) & (ll <= MAX_LAG)
            ll = np.clip(ll, 1, MAX_LAG)
            r = c.M[MAX_LAG + ll, a, b]
            same = valid & (np.sign(r) == sign)
            better = same & (np.isnan(best) | (np.abs(r) > np.abs(best)))
            best = np.where(better, r, best)
            sig |= same & (np.abs(r) >= c.rep_threshold)
        rvals.iloc[idx, rvals.columns.get_loc(name)] = best
        hits[idx] += sig
        tested[idx] += 1
    return hits, rvals, tested


def add_replication(pairs: pd.DataFrame, others: dict[str, Country]) -> pd.DataFrame:
    """reps, the countries tested, and the chance of that many reps under the null."""
    reps, rvals, tested = replicates(pairs, others)
    pairs = pairs.assign(reps=reps, tested=tested)
    pairs["p_rep"] = stats.binom.sf(reps - 1, tested, REP_ALPHA)
    return pairs, rvals


def rank(pairs: pd.DataFrame) -> pd.DataFrame:
    pairs = pairs.assign(abs_r=pairs.r.abs())
    return pairs.sort_values(["reps", "abs_r"], ascending=False)


# --------------------------------------------------------------------------- weekday


def weekday_volume(country_data: Path, year: int) -> pd.Series:
    """Articles per weekday in `year`, from every source's news.csv."""
    counts = pd.Series(0, index=range(7), dtype=float)
    for f in sorted(country_data.glob("*/news.csv")):
        try:
            d = pd.read_csv(f, usecols=["date"], on_bad_lines="skip")["date"]
        except (ValueError, pd.errors.ParserError):
            continue
        d = pd.to_datetime(d, errors="coerce", format="mixed").dropna()
        d = d[d.dt.year == year]
        counts = counts.add(d.dt.weekday.value_counts(), fill_value=0)
    return counts


def weekday_share(countries: dict[str, Path]) -> pd.DataFrame:
    """Daily-tail weekday profile, pooled over countries.

    Volume = articles that day; share = articles matching any group / articles,
    each as a ratio to the country's tail mean, then averaged over countries.
    """
    rows = []
    for name, cdir in countries.items():
        f = cdir / "uncertainty_attribution" / "groups_pooled.csv"
        if not f.exists():
            continue
        d = pd.read_csv(f)
        d["date"] = pd.to_datetime(d["date"])
        if d["A_total"].sum() < 50:
            continue
        g_cols = [c for c in d.columns if c.startswith("G_")]
        vol = d["A_total"] / d["A_total"].mean()
        share = d[g_cols].sum(axis=1) / d["A_total"].where(d["A_total"] > 0)
        share = share / share.mean()
        rows.append(
            pd.DataFrame(
                {
                    "country": name,
                    "weekday": d.date.dt.weekday,
                    "vol": vol,
                    "share": share,
                }
            )
        )
    return pd.concat(rows) if rows else pd.DataFrame()


# --------------------------------------------------------------------------- report

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def text_page(pdf: PdfPages, title: str, body: str, size: float = 10):
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.text(0.08, 0.95, title, fontsize=16, weight="bold", va="top")
    fig.text(0.08, 0.91, body, fontsize=size, va="top", family="monospace", wrap=True)
    pdf.savefig(fig)
    plt.close(fig)


def pair_page(
    pdf: PdfPages,
    title: str,
    home: Country,
    a: str,
    b: str,
    names: dict[str, str],
    rvals: pd.Series | None,
    note: str,
):
    """Raw series, aligned YoY series, CCF bars and the replication strip."""
    fig, axes = plt.subplots(
        4, 1, figsize=(8.27, 11.69), gridspec_kw={"height_ratios": [1, 1, 1, 1.1]}
    )
    fig.suptitle(
        textwrap.fill(title, 70), fontsize=12, weight="bold", x=0.08, ha="left"
    )
    fig.text(0.08, 0.94, note, fontsize=9, va="top")

    ax = axes[0]
    for item, color in ((a, "#c0392b"), (b, "#2c3e50")):
        if item in home.raw:
            s = home.raw[item].rolling(3, min_periods=1).mean()
            ax.plot(s.index, s, color=color, lw=1.2, label=pretty(item, names))
    ax.axhline(100, color="#999", lw=0.6, ls=":")
    ax.set_title("Index (2024 = 100), 3-month rolling mean", fontsize=9, loc="left")
    ax.legend(fontsize=8, loc="upper left")

    ccf = home.ccf(a, b)
    ax = axes[1]
    if ccf is not None:
        lag = MAX_LAG + 1 + int(np.abs(ccf[MAX_LAG + 1 :]).argmax())
        k = lag - MAX_LAG
        R = home.R
        ax.plot(R.index, R[b], color="#2c3e50", lw=0.9, label=f"{pretty(b, names)}")
        ax.plot(
            R.index,
            R[a].shift(k),
            color="#c0392b",
            lw=0.9,
            alpha=0.8,
            label=f"{pretty(a, names)}, shifted +{k} mo",
        )
        ax.legend(fontsize=8, loc="upper left")
    ax.set_title(
        "Prewhitened year-over-year changes (z), leader shifted by best lag",
        fontsize=9,
        loc="left",
    )

    ax = axes[2]
    if ccf is not None:
        lags = np.arange(-MAX_LAG, MAX_LAG + 1)
        crit = np.full(len(lags), np.quantile(home.null_peaks, 0.95))
        colors = ["#c0392b" if lag > 0 else "#7f8c8d" for lag in lags]
        ax.bar(lags, ccf, color=colors)
        ax.plot(lags, crit, color="#e67e22", lw=0.8, ls="--")
        ax.plot(lags, -crit, color="#e67e22", lw=0.8, ls="--")
        ax.axhline(0, color="black", lw=0.5)
        ax.set_xticks(lags)
    ax.set_title(
        "Cross-correlation by lag (positive = first series leads); "
        "dashed = 95th pct of scrambled peaks",
        fontsize=9,
        loc="left",
    )

    ax = axes[3]
    if rvals is not None and rvals.notna().any():
        rv = rvals.dropna().sort_values()
        ax.barh(range(len(rv)), rv.to_numpy(), color="#34495e")
        ax.set_yticks(range(len(rv)))
        ax.set_yticklabels([c.replace("_", " ") for c in rv.index], fontsize=6)
        ax.axvline(0, color="black", lw=0.5)
    ax.set_title(
        "Same pair in other LAC countries: best same-sign r at lag +/-1",
        fontsize=9,
        loc="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    pdf.savefig(fig)
    plt.close(fig)


def table_page(pdf: PdfPages, title: str, df: pd.DataFrame, note: str = ""):
    fig = plt.figure(figsize=(11.69, 8.27))
    fig.text(0.04, 0.96, title, fontsize=14, weight="bold", va="top")
    if note:
        fig.text(0.04, 0.92, note, fontsize=9, va="top")
    ax = fig.add_axes((0.02, 0.02, 0.96, 0.86))
    ax.axis("off")
    if len(df):
        t = ax.table(
            cellText=df.astype(str).to_numpy(),
            colLabels=list(df.columns),
            loc="upper center",
            cellLoc="left",
        )
        t.auto_set_font_size(False)
        t.set_fontsize(7)
        t.auto_set_column_width(range(len(df.columns)))
    else:
        ax.text(0.5, 0.9, "None.", ha="center", fontsize=11)
    pdf.savefig(fig)
    plt.close(fig)


def heatmap_page(pdf: PdfPages, title: str, rv: pd.DataFrame, row_labels: list[str]):
    fig, ax = plt.subplots(figsize=(11.69, 8.27))
    data = rv.to_numpy(dtype=float)
    im = ax.imshow(data, aspect="auto", cmap="RdBu_r", vmin=-0.5, vmax=0.5)
    ax.set_yticks(range(len(row_labels)))
    ax.set_yticklabels(row_labels, fontsize=6)
    ax.set_xticks(range(rv.shape[1]))
    ax.set_xticklabels(
        [c.replace("_", " ") for c in rv.columns], rotation=90, fontsize=6
    )
    ax.set_title(title, fontsize=12, loc="left")
    fig.colorbar(
        im, ax=ax, shrink=0.6, label="best same-sign r (blank = series too sparse)"
    )
    fig.tight_layout()
    pdf.savefig(fig)
    plt.close(fig)


def weekday_page(
    pdf: PdfPages, vol: pd.Series, year: int, home: str, tail: pd.DataFrame
):
    fig, axes = plt.subplots(2, 1, figsize=(8.27, 11.69))
    fig.suptitle("Weekday check", fontsize=14, weight="bold", x=0.08, ha="left")
    ax = axes[0]
    if vol.sum():
        ratio = vol / vol.mean()
        ax.bar(DAYS, ratio.to_numpy(), color="#34495e")
        ax.axhline(1, color="#999", lw=0.6, ls=":")
        for i, v in enumerate(ratio):
            ax.text(i, v, f"{v:.2f}", ha="center", va="bottom", fontsize=8)
    ax.set_title(
        f"{home.capitalize()}, articles per weekday in {year} (ratio to mean), "
        f"n = {int(vol.sum()):,}",
        fontsize=9,
        loc="left",
    )
    ax = axes[1]
    if len(tail):
        g = tail.groupby("weekday")[["vol", "share"]].mean().reindex(range(7))
        x = np.arange(7)
        ax.bar(x - 0.2, g["vol"], width=0.4, label="article volume", color="#95a5a6")
        ax.bar(
            x + 0.2,
            g["share"],
            width=0.4,
            label="share matching any group",
            color="#c0392b",
        )
        ax.axhline(1, color="#999", lw=0.6, ls=":")
        ax.set_xticks(x)
        ax.set_xticklabels(DAYS)
        ax.legend(fontsize=8)
    days = tail["weekday"].nunique() if len(tail) else 0
    ax.set_title(
        f"LAC daily tail ({tail['country'].nunique() if len(tail) else 0} countries, "
        f"current month only, {days} weekdays covered): ratio to each country's mean",
        fontsize=9,
        loc="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    pdf.savefig(fig)
    plt.close(fig)


# --------------------------------------------------------------------------- main


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--region", default="lac")
    ap.add_argument("--country", default="argentina")
    ap.add_argument("--measure", default="intensity", choices=list(MEASURE_LABELS))
    ap.add_argument("--weekday-year", type=int, default=2024)
    args = ap.parse_args()

    schema = json.loads((OUT / "dashboard_data" / "keywords_schema.json").read_text())
    names = labels(schema)
    ancestors = group_ancestors(schema)
    members = group_concepts(schema)
    dirs = country_dirs(args.region)
    home_name = args.country
    print(f"{len(dirs)} countries in {args.region}")

    # Groups everywhere.
    groups = {
        n: Country(
            load_series(d, "groups", args.measure),
            HOME_SHIFTS if n == args.country else OTHER_SHIFTS,
        )
        for n, d in dirs.items()
    }
    home = groups[home_name]
    others = {n: c for n, c in groups.items() if n != home_name}
    nested = {
        (a, b)
        for a in home.items
        for b in home.items
        if b in ancestors.get(a, ()) or a in ancestors.get(b, ())
    }
    pairs = scan(home, exclude=nested)
    pairs, rvals = add_replication(pairs, others)
    pairs = rank(pairs)

    # Placebo: the whole home scan on timing-scrambled copies of the same series.
    placebo = []
    for seed in (101, 102, 103):
        R = pd.DataFrame(
            circular_shift(home.R.to_numpy(), np.random.default_rng(seed)),
            index=home.R.index,
            columns=home.R.columns,
        )
        placebo.append(
            int(
                scan(
                    Country(home.raw, HOME_SHIFTS, seed, R=R), exclude=nested
                ).fdr.sum()
            )
        )
    survivors = pairs[pairs.fdr & (pairs.reps >= MIN_REPS)]
    near = pairs[
        (pairs.fdr & (pairs.reps < MIN_REPS)) | (~pairs.fdr & (pairs.reps >= MIN_REPS))
    ]
    top = survivors.head(TOP_N)
    # With no survivors, still show the strongest candidates, clearly labelled.
    shown = top if len(top) else pairs.sort_values("p").head(5)
    print(
        f"groups: {len(home.items)} eligible, {len(pairs)} lead pairs, "
        f"{int(pairs.fdr.sum())} pass FDR (placebo {placebo}), {len(survivors)} also replicate"
    )

    # Concepts: the worked example plus drill-down inside the top group pairs.
    needed = set(EXAMPLE_CONCEPTS)
    for a, b in zip(top.leader, top.follower):
        needed |= set(members.get(a, [])) | set(members.get(b, []))
    concepts = {}
    for n, d in dirs.items():
        raw = load_series(d, "concepts", args.measure)
        concepts[n] = Country(raw[[c for c in raw.columns if c in needed]])
    chome = concepts[home_name]
    cothers = {n: c for n, c in concepts.items() if n != home_name}

    drill = []
    for gi, (a, b) in enumerate(zip(top.leader, top.follower)):
        ca = [c for c in members.get(a, []) if c in chome.pos]
        cb = [c for c in members.get(b, []) if c in chome.pos]
        rows = []
        for x in ca:
            for y in cb:
                if x == y:
                    continue
                ccf = chome.ccf(x, y)
                lag = int(np.abs(ccf).argmax()) - MAX_LAG
                if lag <= 0:
                    continue
                r = ccf[MAX_LAG + lag]
                p = chome.peak_p(r)
                rows.append(
                    {
                        "group_pair": gi + 1,
                        "leader": x,
                        "follower": y,
                        "lag": lag,
                        "r": r,
                        "p": p,
                    }
                )
        if rows:
            drill.append(pd.DataFrame(rows))
    drill = (
        pd.concat(drill, ignore_index=True)
        if drill
        else pd.DataFrame(columns=["group_pair", "leader", "follower", "lag", "r", "p"])
    )
    if len(drill):
        drill["fdr"] = bh_reject(drill.p.to_numpy(), FDR)
        drill, _ = add_replication(drill, cothers)
        drill = rank(drill)

    # Worked example, in the chosen measure and the other main one. Tested
    # even when sparse, so the page always shows the pair; the note says so.
    examples = []
    for measure in dict.fromkeys(
        [args.measure, "absolute" if args.measure == "intensity" else "intensity"]
    ):
        ex_c, ex_g = {}, {}
        for n, d in dirs.items():
            raw = load_series(d, "concepts", measure)
            ex_c[n] = Country(
                raw[[x for x in raw.columns if x in EXAMPLE_CONCEPTS]], min_nonzero=0
            )
            raw = load_series(d, "groups", measure)
            ex_g[n] = Country(
                raw[[x for x in raw.columns if x in EXAMPLE_GROUPS]], min_nonzero=0
            )
        g, c = ex_g[home_name], ex_c[home_name]
        go = {n: v for n, v in ex_g.items() if n != home_name}
        co = {n: v for n, v in ex_c.items() if n != home_name}
        for level, (a, b), country, oth in (
            ("concept", EXAMPLE_CONCEPTS, c, co),
            ("group", EXAMPLE_GROUPS, g, go),
        ):
            ccf = country.ccf(a, b)
            ex = {
                "measure": measure,
                "level": level,
                "a": a,
                "b": b,
                "country": country,
            }
            if ccf is None:
                ex[
                    "note"
                ] = "One of the two series is too sparse to test (non-zero in < 80% of months)."
                ex["rvals"] = None
            else:
                peak = int(np.abs(ccf).argmax()) - MAX_LAG
                r = ccf[MAX_LAG + peak]
                p = country.peak_p(r)
                lead = max(1, abs(peak))
                one = pd.DataFrame(
                    {
                        "leader": [a],
                        "follower": [b],
                        "lag": [lead],
                        "r": [ccf[MAX_LAG + lead]],
                    }
                )
                reps, rv, tested = replicates(one, oth)
                direction = (
                    f"{a} leads by {peak} mo"
                    if peak > 0
                    else f"{b} leads by {-peak} mo"
                    if peak < 0
                    else "same month"
                )
                dense = (country.raw[[a, b]].fillna(0) > 0).mean()
                sparse = (
                    f"Sparse: non-zero in {dense[a]:.0%} / {dense[b]:.0%} of months "
                    f"(main scan needs {MIN_NONZERO:.0%}); treat as indicative.\n"
                    if dense.min() < MIN_NONZERO
                    else ""
                )
                ex["note"] = sparse + (
                    f"Peak r = {r:+.2f} at lag {peak:+d} ({direction}); permutation p = {p:.3f}; "
                    f"lag 0 r = {ccf[MAX_LAG]:+.2f}.\n"
                    f"At lag +{lead}: r = {ccf[MAX_LAG + lead]:+.2f}; repeats in {int(reps[0])} other LAC countries "
                    f"of {int(tested[0])} tested"
                    f" (chance alone gives about {tested[0] * REP_ALPHA:.1f})."
                )
                ex["rvals"] = rv.iloc[0]
            examples.append(ex)

    # Weekday check.
    vol = weekday_volume(
        DATA / args.region / dirs[home_name].relative_to(OUT / args.region),
        args.weekday_year,
    )
    tail = weekday_share(dirs)

    # ------------------------------------------------------------------ write PDF
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = (
        REPORT_DIR / f"{date.today():%Y-%m-%d}-lead-lag-{home_name}-{args.measure}.pdf"
    )
    first, last = home.R.index.min(), home.R.index.max()
    with PdfPages(out) as pdf:
        text_page(
            pdf,
            f"Lead-lag exploration: {home_name.capitalize()}",
            f"""Measure: {args.measure}  ("{MEASURE_LABELS[args.measure]}" in the dashboard)
Region for replication: {args.region.upper()}, {len(others)} other countries
Data: monthly index series, global-concepts build of 12 Oct 2026 (Mac)
Tested window after differencing: {first:%Y-%m} .. {last:%Y-%m} ({home.n} months)

METHOD
1. Log of each monthly index, minus its month-of-year mean
   (removes the yearly cycle), then the monthly change.
2. Prewhiten each series with its own AR model (lags 1-3 and 12,
   chosen by AIC), so a series' own memory cannot fake a lead.
3. Replace values by their ranks, so one spike month (e.g. COVID)
   weighs no more than any other month.
4. Cross-correlate every ordered pair at lags -{MAX_LAG}..+{MAX_LAG} months.
   "A leads B" when the largest |r| sits at a positive lag.
5. p-value = share of {HOME_SHIFTS} timing-scrambled copies (each series
   rolled by a random offset) with a peak at least as large.
   Then Benjamini-Hochberg false-discovery rate {FDR:.0%} over all pairs.
6. Replication: same pair, same sign, lag +/-1, beating the 95th
   percentile of that country's own scrambled copies. A signal needs
   >= {MIN_REPS} replicating countries. p_rep = chance of that many
   replications if nothing were there (about 5% of countries by luck).
Series kept only if non-zero in >= {MIN_NONZERO:.0%} of months.
Group pairs where one group contains the other are excluded.

WHY SCRAMBLED COPIES
A first version used textbook p-values on year-over-year changes.
It passed 906 pairs, but the same scan on timing-scrambled data still
passed 446: those p-values were far too optimistic. The method above
passes about as many pairs on scrambled data as the textbook test
promises (a handful), so its real-data count can be trusted.

RESULTS (groups)
Eligible groups in {home_name}:       {len(home.items)}
Ordered lead pairs tested:           {len(pairs):,}
Pass FDR in {home_name}:              {int(pairs.fdr.sum())}
Same scan on 3 scrambled copies:     {placebo}
Pass FDR and replicate in >= {MIN_REPS}:      {len(survivors)}
Near misses (one bar only):           {len(near)}
Concept drill-down pairs (top {len(top)}):  {len(drill)}, {int(drill.fdr.sum()) if len(drill) else 0} pass FDR

READING THE PAIR PAGES
Top: both indices (3-month mean). Middle: the prewhitened, ranked
changes with the leader shifted by its best lag. Bars: correlation
at each lag; red = leader-first lags, dashed = 95th percentile of
peaks in scrambled copies.
Bottom: the same pair's r in every other LAC country.

LIMITS
- Correlation at a lag is not causation; a third topic (e.g. an
  election or a budget cycle) can drive both.
- Monthly grain only. Weekly lags need weekly history (idea 3).
- Replication across neighbours can share the same news events.
""",
            size=8.5,
        )

        for ex in examples:
            pair_page(
                pdf,
                f"Worked example ({ex['level']}, {ex['measure']}): "
                f"{pretty(ex['a'], names)} -> {pretty(ex['b'], names)}",
                ex["country"],
                ex["a"],
                ex["b"],
                names,
                ex["rvals"],
                ex["note"],
            )

        candidate = "" if len(top) else "Not significant, strongest candidate "
        for i, row in enumerate(shown.itertuples(), 1):
            pair_page(
                pdf,
                f"{candidate}#{i}  {pretty(row.leader, names)} -> {pretty(row.follower, names)}",
                home,
                row.leader,
                row.follower,
                names,
                rvals.loc[row.Index],
                f"Lag +{row.lag} mo, r = {row.r:+.2f} (same month r = {row.r0:+.2f}), "
                f"permutation p = {row.p:.2g}, passes FDR: {row.fdr}; repeats in {row.reps} of "
                f"{row.tested} other LAC countries (chance: {row.tested * REP_ALPHA:.1f}, p_rep = {row.p_rep:.2g}).",
            )

        heatmap_page(
            pdf,
            f"Replication across LAC countries: {'top pairs' if len(top) else 'strongest candidates'}",
            rvals.loc[shown.index],
            [
                f"#{i} {pretty(a, names)} -> {pretty(b, names)} (+{lag})"
                for i, (a, b, lag) in enumerate(
                    zip(shown.leader, shown.follower, shown.lag), 1
                )
            ],
        )

        if len(drill):
            show = (
                drill.groupby("group_pair")
                .head(5)
                .sort_values(
                    ["group_pair", "reps", "abs_r"], ascending=[True, False, False]
                )
            )
            table_page(
                pdf,
                "Concept drill-down inside the top group pairs (top 5 per pair)",
                show.assign(r=show.r.round(2), p=show.p.map(lambda v: f"{v:.2g}"))[
                    [
                        "group_pair",
                        "leader",
                        "follower",
                        "lag",
                        "r",
                        "p",
                        "fdr",
                        "reps",
                        "tested",
                    ]
                ].head(60),
                "group_pair = number of the group pair page. fdr = passes 5% FDR within the drill-down set.",
            )

        near_show = near.head(30)
        table_page(
            pdf,
            "Near misses: pass one bar but not both",
            near_show.assign(
                leader=near_show.leader.map(lambda x: pretty(x, names)),
                follower=near_show.follower.map(lambda x: pretty(x, names)),
                r=near_show.r.round(2),
                p=near_show.p.map(lambda v: f"{v:.2g}"),
                p_rep=near_show.p_rep.map(lambda v: f"{v:.2g}"),
            )[
                [
                    "leader",
                    "follower",
                    "lag",
                    "r",
                    "p",
                    "fdr",
                    "reps",
                    "tested",
                    "p_rep",
                ]
            ],
            f"fdr = passes 5% FDR in {home_name}; reps = replicating LAC countries (bar: >= {MIN_REPS}) "
            f"out of tested; p_rep = chance of that many by luck. Top 30.",
        )

        weekday_page(pdf, vol, args.weekday_year, home_name, tail)

    pairs.to_csv(out.with_suffix(".pairs.csv"), index=False)
    if len(drill):
        drill.to_csv(out.with_suffix(".concepts.csv"), index=False)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
