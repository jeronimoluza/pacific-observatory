"""Narrative mining on weekly group counts: bursts, same-week bundles, spread.

Reads the daily-history build (``text build --daily-history``) through
``weekly.weekly`` (same masking, Monday-Sunday weeks, share of articles).

1. Bursts. A group bursts in a week when its count is at least
   ``BURST_RATIO`` times the count expected from its share over the previous
   ``BASE_WEEKS`` weeks, at least ``BURST_MIN`` articles, and Poisson
   p < ``BURST_P``. Runs of burst weeks (gaps of ``GAP`` allowed) are
   episodes, with a peak, a rise, a decay (weeks until half the peak excess)
   and a shape. Episodes longer than ``LONG`` weeks, or still above 1.5x the
   baseline ``TAIL`` weeks after the peak, are level shifts (often a source
   entering), and are left out of narratives. Weeks where more than ``BROAD``
   of a country's groups burst are flagged as broad (volume or source change).
   Narrative episodes: a country's group peaks within ``WINDOW`` weeks of each
   other. Recurring pairs: groups that burst together in many episodes.
2. Bundles. Per country: log share with a centred ``HP_WEEKS`` rolling mean
   removed (drops level shifts and slow trends), then log articles and log
   active sources regressed out. Same-week correlations, Fisher-z pooled over
   countries (weights n - 3), p from circularly shifted copies, BH 5%.
   Parent-child group pairs are left out. Bundles: average-linkage clusters of
   the significant positive correlations, cut at mean r ``CUT_R``. Graphical
   lasso on the pooled matrix marks which edges are direct. Bundle strength
   per subregion, per country and per year.
3. Spread. Regional bursts: weeks where a group peaks in at least
   ``SYNC_MIN`` countries within one week, tested against each country's peaks
   shifted in time. Country co-burst lift: same group peaking within one week,
   observed / shifted. Variance shares of each group's residual series
   explained by the SSA mean and the subregion mean (leave-one-out).

Writes a PDF and CSVs to outputs/text/reports/concepts-exploration-pdfs/.

Run: python src/text/analysis/explorations/narratives.py [--region ssa]
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from itertools import combinations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from scipy.cluster.hierarchy import fcluster, linkage  # noqa: E402
from scipy.spatial.distance import squareform  # noqa: E402
from scipy.stats import poisson  # noqa: E402
from sklearn.covariance import graphical_lasso  # noqa: E402

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
from weekly import MIN_COUNTRIES, weekly  # noqa: E402

MIN_TOTAL = 50  # articles over the whole series, for a group to be scanned
BASE_WEEKS = 26
BASE_MIN = 13
BURST_RATIO = 2.5
BURST_MIN = 5
BURST_P = 1e-4
GAP = 1
TAIL = 12
LONG = 8
BROAD = 0.10
WINDOW = 2
PAIR_MIN = 5  # episodes for a recurring pair
HP_WEEKS = 13
COMMON_PCS = 1
MIN_ACTIVE = 0.3  # share of valid weeks with a mention, for bundles
NULL_DRAWS = 20
FDR = 0.05
CUT_R = 0.15
GLASSO_ALPHA = 0.02
SYNC_MIN = 3
ALLAFRICA_START = pd.Timestamp("2026-03-30")


# --------------------------------------------------------------------------- 1. bursts


def bursts(w: dict):
    """Burst flags, counts, expected counts and baseline shares per week."""
    A = w["articles"]
    G = w["counts"]
    G = G.loc[:, G.sum() >= MIN_TOTAL].where(A.notna(), axis=0)
    gs = G.shift(1).rolling(BASE_WEEKS, min_periods=BASE_MIN).sum()
    at = A.shift(1).rolling(BASE_WEEKS, min_periods=BASE_MIN).sum()
    base = (gs + 0.5).div(at + 1, axis=0)
    exp = base.mul(A, axis=0)
    p = pd.DataFrame(
        poisson.sf(G.to_numpy() - 1, exp.to_numpy()), index=G.index, columns=G.columns
    )
    hit = (G >= BURST_MIN) & (G >= BURST_RATIO * exp) & (p < BURST_P)
    return hit, G, exp, base


def shape(r) -> str:
    if r.weeks > LONG or r.tail_ratio > 1.5:
        return "level shift"
    if r.rise >= 2:
        return "build-up"
    if r.decay <= 1:
        return "spike"
    return "slow fade"


def episodes(name: str, sub: str, w: dict) -> tuple[pd.DataFrame, pd.Series]:
    hit, G, exp, base = bursts(w)
    A = w["articles"]
    breadth = hit.sum(axis=1) / max(hit.shape[1], 1)
    weeks = hit.index
    H, Gv, Ev, Bv = hit.to_numpy(), G.to_numpy(), exp.to_numpy(), base.to_numpy()
    Av = A.to_numpy()
    rows = []
    for j, g in enumerate(hit.columns):
        idx = np.flatnonzero(H[:, j])
        if not len(idx):
            continue
        for run in np.split(idx, np.flatnonzero(np.diff(idx) > GAP + 1) + 1):
            s, e = run[0], run[-1]
            pk = s + int(np.nanargmax(Gv[s : e + 1, j] / Ev[s : e + 1, j]))
            after = Gv[pk : pk + TAIL + 1, j] / Av[pk : pk + TAIL + 1] / Bv[s, j]
            pr = after[0]
            below = np.flatnonzero(after <= 1 + (pr - 1) / 2)
            rows.append(
                {
                    "country": name,
                    "subregion": sub,
                    "group": g,
                    "start": weeks[s],
                    "peak": weeks[pk],
                    "end": weeks[e],
                    "weeks": e - s + 1,
                    "rise": pk - s,
                    "decay": below[0] if len(below) else np.nan,
                    "peak_ratio": pr,
                    "peak_count": int(Gv[pk, j]),
                    "excess": float(
                        np.nansum(np.clip(Gv[s : e + 1, j] - Ev[s : e + 1, j], 0, None))
                    ),
                    "tail_ratio": np.nanmean(after[-4:])
                    if len(after) > TAIL
                    else np.nan,
                    "broad": breadth.iloc[pk] > BROAD,
                }
            )
    ep = pd.DataFrame(rows)
    if len(ep):
        ep["shape"] = [shape(r) for r in ep.itertuples()]
    return ep, breadth


def narratives(ep: pd.DataFrame) -> pd.DataFrame:
    """Group peaks within WINDOW weeks of the first, per country."""
    out = []
    step = pd.Timedelta(weeks=WINDOW)
    for country, d in ep.groupby("country"):
        d = d.sort_values("peak")
        peaks = pd.DatetimeIndex(d.peak)
        i = 0
        while i < len(d):
            j = int(peaks.searchsorted(peaks[i] + step, side="right"))
            chunk = d.iloc[i:j].sort_values("excess", ascending=False)
            out.append(
                {
                    "country": country,
                    "subregion": chunk.subregion.iloc[0],
                    "week": chunk.peak.min(),
                    "n_groups": len(chunk),
                    "excess": chunk.excess.sum(),
                    "groups": list(chunk.group),
                }
            )
            i = j
    return pd.DataFrame(out)


def recurring_pairs(nar: pd.DataFrame, related) -> pd.DataFrame:
    N = len(nar)
    n_a = pd.Series([g for gs in nar.groups for g in set(gs)]).value_counts()
    pair_n, pair_c = {}, {}
    for r in nar[nar.n_groups >= 2].itertuples():
        for a, b in combinations(sorted(set(r.groups)), 2):
            if related(a, b):
                continue
            pair_n[(a, b)] = pair_n.get((a, b), 0) + 1
            pair_c.setdefault((a, b), set()).add(r.country)
    rows = [
        {
            "a": a,
            "b": b,
            "episodes": n,
            "countries": len(pair_c[(a, b)]),
            "lift": n * N / (n_a[a] * n_a[b]),
        }
        for (a, b), n in pair_n.items()
        if n >= PAIR_MIN
    ]
    df = pd.DataFrame(rows, columns=["a", "b", "episodes", "countries", "lift"])
    return df.sort_values(["lift", "episodes"], ascending=False).reset_index(drop=True)


# --------------------------------------------------------------------------- 2. bundles


def high_pass(x):
    return x - x.rolling(HP_WEEKS, center=True, min_periods=HP_WEEKS // 2 + 1).mean()


def residuals(w: dict) -> pd.DataFrame:
    """High-passed log shares with volume and source count regressed out, z-scored."""
    sh, A = w["shares"], w["articles"]
    ok = A.notna()
    active = (sh[ok].fillna(0) > 0).mean()
    items = list(active.index[active >= MIN_ACTIVE])
    if len(items) < 2:
        return pd.DataFrame()
    span = slice(A.first_valid_index(), A.last_valid_index())
    G, A, S = w["counts"][items].loc[span], A.loc[span], w["sources"].loc[span]
    L = high_pass(np.log((G + 0.5).div(A + 1, axis=0)))
    X = pd.DataFrame({"a": high_pass(np.log(A)), "s": high_pass(np.log(S + 1))})
    rows = L.notna().all(axis=1) & X.notna().all(axis=1)
    L, X = L[rows], X[rows]
    Xm = np.column_stack([np.ones(len(X)), X.to_numpy()])
    beta, *_ = np.linalg.lstsq(Xm, L.to_numpy(), rcond=None)
    R = L.to_numpy() - Xm @ beta
    R = R - R.mean(axis=0)
    u, sv, vt = np.linalg.svd(R / (R.std(axis=0) + 1e-12), full_matrices=False)
    for k in range(COMMON_PCS):  # the country's own common factor
        f = u[:, k]
        R = R - np.outer(f, f @ R)
    sd = R.std(axis=0)
    keep = sd > 0
    R = (R[:, keep] - R[:, keep].mean(axis=0)) / sd[keep]
    return pd.DataFrame(R, index=L.index, columns=np.array(items)[keep])


class SameWeek:
    """Weighted mean Fisher-z of same-week correlations over countries."""

    def __init__(self, items: list[str]):
        self.items = items
        self.pos = {c: i for i, c in enumerate(items)}
        k = len(items)
        self.zsum = np.zeros((k, k))
        self.wsum = np.zeros((k, k))
        self.n = np.zeros((k, k), np.int16)

    def add(self, R: pd.DataFrame, X: np.ndarray | None = None):
        X = R.to_numpy() if X is None else X
        if len(X) < 30:
            return
        idx = np.ix_(*[np.array([self.pos[c] for c in R.columns])] * 2)
        C = X.T @ X / len(X)
        self.zsum[idx] += (len(X) - 3) * np.arctanh(np.clip(C, -0.999, 0.999))
        self.wsum[idx] += len(X) - 3
        self.n[idx] += 1

    def r(self, min_n: int = MIN_COUNTRIES) -> np.ndarray:
        with np.errstate(invalid="ignore", divide="ignore"):
            r = np.tanh(self.zsum / self.wsum)
        r[(self.n < min_n) | np.eye(len(self.items), dtype=bool)] = np.nan
        return r


def shifted(X: np.ndarray, rng) -> np.ndarray:
    n = len(X)
    return np.column_stack(
        [np.roll(X[:, j], rng.integers(4, n - 4)) for j in range(X.shape[1])]
    )


def bundles(res: dict, items, related, draws: int):
    pool = SameWeek(items)
    for R in res.values():
        pool.add(R)
    r = pool.r()
    rng = np.random.default_rng(11)
    null = []
    for _ in range(draws):
        p0 = SameWeek(items)
        for R in res.values():
            p0.add(R, shifted(R.to_numpy(), rng))
        null.append(np.abs(p0.r()[np.triu_indices(len(items), 1)]))
    null = np.concatenate(null)
    null = null[~np.isnan(null)]
    iu = np.triu_indices(len(items), 1)
    ok = ~np.isnan(r[iu]) & np.array(
        [not related(items[a], items[b]) for a, b in zip(*iu)]
    )
    ia, ib = iu[0][ok], iu[1][ok]
    p = emp_p(np.abs(r[ia, ib]), null)
    edges = pd.DataFrame(
        {
            "a": [items[k] for k in ia],
            "b": [items[k] for k in ib],
            "r": r[ia, ib],
            "countries": pool.n[ia, ib],
            "p": p,
        }
    )
    edges["fdr"] = bh_reject(p, FDR)

    # Graphical lasso on the pooled matrix, items present in enough countries.
    present = np.diag(pool.n) >= MIN_COUNTRIES
    sub = [items[k] for k in np.flatnonzero(present)]
    C = np.nan_to_num(r[np.ix_(present, present)])
    np.fill_diagonal(C, 1)
    vals, vecs = np.linalg.eigh(C)
    C = vecs @ np.diag(np.clip(vals, 1e-3, None)) @ vecs.T
    d = np.sqrt(np.diag(C))
    C = C / np.outer(d, d)
    _, P = graphical_lasso(C, alpha=GLASSO_ALPHA, max_iter=200)
    pd_ = np.sqrt(np.diag(P))
    partial = -P / np.outer(pd_, pd_)
    ppos = {c: i for i, c in enumerate(sub)}
    edges["partial_r"] = [
        partial[ppos[a], ppos[b]] if a in ppos and b in ppos else np.nan
        for a, b in zip(edges.a, edges.b)
    ]

    # Clusters on significant positive correlations.
    S = np.zeros((len(items), len(items)))
    sig = edges[edges.fdr & (edges.r > 0)]
    for a, b, v in zip(sig.a, sig.b, sig.r):
        S[pool.pos[a], pool.pos[b]] = S[pool.pos[b], pool.pos[a]] = v
    linked = np.flatnonzero(S.any(axis=1))
    if len(linked) < 2:
        return edges, pd.DataFrame(), null
    Ds = 1 - S[np.ix_(linked, linked)]
    np.fill_diagonal(Ds, 0)
    lab = fcluster(linkage(squareform(Ds), "average"), 1 - CUT_R, "distance")
    rows = []
    for c in np.unique(lab):
        mem = linked[lab == c]
        if len(mem) < 3:
            continue
        sub_s = S[np.ix_(mem, mem)]
        deg = sub_s.sum(axis=1)
        order = mem[np.argsort(-deg)]
        rows.append(
            {
                "members": [items[k] for k in order],
                "size": len(mem),
                "mean_r": sub_s[np.triu_indices(len(mem), 1)].mean(),
            }
        )
    bund = pd.DataFrame(rows).sort_values("mean_r", ascending=False)
    bund.insert(0, "bundle", [f"B{i + 1}" for i in range(len(bund))])
    return edges, bund.reset_index(drop=True), null


def bundle_strength(R: pd.DataFrame, members) -> float:
    m = [c for c in members if c in R.columns]
    if len(m) < 2 or len(R) < 30:
        return np.nan
    C = np.corrcoef(R[m].to_numpy().T)
    return float(C[np.triu_indices(len(m), 1)].mean())


# --------------------------------------------------------------------------- 3. spread


def peak_panel(ep: pd.DataFrame, weeks, groups, countries) -> np.ndarray:
    """P[country, week, group] = 1 at the peak of a non-level-shift episode."""
    P = np.zeros((len(countries), len(weeks), len(groups)), np.float32)
    wpos = {w: i for i, w in enumerate(weeks)}
    gpos = {g: i for i, g in enumerate(groups)}
    cpos = {c: i for i, c in enumerate(countries)}
    for r in ep.itertuples():
        P[cpos[r.country], wpos[r.peak], gpos[r.group]] = 1
    return P


def widen(P: np.ndarray) -> np.ndarray:
    """Peak +/- 1 week."""
    W = P.copy()
    W[:, 1:] = np.maximum(W[:, 1:], P[:, :-1])
    W[:, :-1] = np.maximum(W[:, :-1], P[:, 1:])
    return W


def time_shift(P: np.ndarray, rng) -> np.ndarray:
    n = P.shape[1]
    return np.stack(
        [np.roll(P[c], rng.integers(8, n - 8), axis=0) for c in range(len(P))]
    )


def regional_events(P, weeks, groups, countries, subs):
    """Runs of weeks where >= SYNC_MIN countries peak within 1 week.

    p: Poisson tail of the count, expected = sum over countries active that week
    of the chance of a peak within +/- 1 week at the country's own rate.
    BH over every (week, group) cell that could hold an event.
    """
    count = widen(P).sum(axis=0)  # week x group
    any_peak = P.any(axis=2)
    first = any_peak.argmax(axis=1)
    last = P.shape[1] - 1 - any_peak[:, ::-1].argmax(axis=1)
    t = np.arange(P.shape[1])
    active = (t >= first[:, None]) & (t <= last[:, None])  # country x week
    rate = P.sum(axis=1) / active.sum(axis=1, keepdims=True)  # country x group
    q = 1 - (1 - rate) ** 3
    lam = active.T.astype(float) @ q  # week x group
    rows = []
    for g in range(len(groups)):
        hot = np.flatnonzero(count[:, g] >= SYNC_MIN)
        if not len(hot):
            continue
        for run in np.split(hot, np.flatnonzero(np.diff(hot) > 1) + 1):
            s, e = run[0], run[-1]
            n = int(count[s : e + 1, g].max())
            members = np.flatnonzero(P[:, max(s - 1, 0) : e + 2, g].any(axis=1))
            first = [
                int(np.flatnonzero(P[c, max(s - 1, 0) : e + 2, g])[0]) for c in members
            ]
            order = members[np.argsort(first, kind="stable")]
            rows.append(
                {
                    "group": groups[g],
                    "week": weeks[s],
                    "countries": n,
                    "members": [countries[c] for c in order],
                    "subregions": len({subs[countries[c]] for c in members}),
                    "expected": lam[s + int(count[s : e + 1, g].argmax()), g],
                    "p": poisson.sf(
                        n - 1, lam[s + int(count[s : e + 1, g].argmax()), g]
                    ),
                    "after_allafrica": weeks[s] >= ALLAFRICA_START,
                }
            )
    ev = pd.DataFrame(rows)
    if len(ev):
        m = int((lam > 0).sum())
        pv = np.concatenate([ev.p.to_numpy(), np.ones(m - len(ev))])
        ev["fdr"] = bh_reject(pv, FDR)[: len(ev)]
        woy = ev.week.dt.isocalendar().week.to_numpy().astype(int)
        yr = ev.week.dt.year.to_numpy()
        ev["calendar"] = [
            bool(
                ((ev.group.to_numpy() == g) & (yr != y) & (np.abs(woy - w) <= 2)).any()
            )
            for g, y, w in zip(ev.group, yr, woy)
        ]
        ev = ev.sort_values(["p", "countries"], ascending=[True, False])
    return ev.reset_index(drop=True)


def coburst_lift(P, draws) -> np.ndarray:
    flat = P.reshape(len(P), -1)
    obs = flat @ widen(P).reshape(len(P), -1).T
    rng = np.random.default_rng(3)
    exp = np.zeros_like(obs)
    for _ in range(draws):
        S = time_shift(P, rng)
        exp += S.reshape(len(P), -1) @ widen(S).reshape(len(P), -1).T
    exp /= draws
    with np.errstate(invalid="ignore", divide="ignore"):
        lift = obs / exp
    np.fill_diagonal(lift, np.nan)
    return lift, obs, exp


def variance_shares(res: dict, subs: dict) -> pd.DataFrame:
    """Per group: R^2 on the leave-one-out SSA mean, then added R^2 of the subregion mean."""
    groups = sorted(set().union(*[set(R.columns) for R in res.values()]))
    rows = []
    for g in groups:
        X = pd.DataFrame({c: R[g] for c, R in res.items() if g in R.columns})
        if X.shape[1] < MIN_COUNTRIES:
            continue
        r2_all, r2_sub = [], []
        for c in X.columns:
            y = X[c].dropna()
            others = X.drop(columns=c).reindex(y.index)
            m = others.mean(axis=1)
            peers = [k for k in others.columns if subs[k] == subs[c]]
            s = others[peers].mean(axis=1) if peers else pd.Series(np.nan, y.index)
            ok = m.notna() & s.notna() if peers else m.notna()
            if ok.sum() < 30:
                continue
            Z1 = np.column_stack([np.ones(ok.sum()), m[ok]])
            Z2 = np.column_stack([Z1, s[ok]]) if peers else Z1
            yy = y[ok].to_numpy()
            tss = ((yy - yy.mean()) ** 2).sum()
            e1 = yy - Z1 @ np.linalg.lstsq(Z1, yy, rcond=None)[0]
            e2 = yy - Z2 @ np.linalg.lstsq(Z2, yy, rcond=None)[0]
            r2_all.append(1 - (e1**2).sum() / tss)
            r2_sub.append((e1**2).sum() / tss - (e2**2).sum() / tss)
        if r2_all:
            rows.append(
                {
                    "group": g,
                    "countries": len(r2_all),
                    "region_share": np.mean(r2_all),
                    "subregion_extra": np.mean(r2_sub),
                }
            )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- report


def heat(pdf, title, data, rows, cols, cmap="viridis", vmin=None, vmax=None, note=""):
    fig, ax = plt.subplots(figsize=(11.69, 8.27))
    im = ax.imshow(data, aspect="auto", cmap=cmap, vmin=vmin, vmax=vmax)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels(rows, fontsize=6)
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels(cols, rotation=90, fontsize=6)
    ax.set_title(title, fontsize=12, loc="left")
    if note:
        fig.text(0.02, 0.01, note, fontsize=8)
    fig.colorbar(im, ax=ax, shrink=0.6)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    pdf.savefig(fig)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--region", default="ssa")
    ap.add_argument("--draws", type=int, default=NULL_DRAWS)
    args = ap.parse_args()

    schema = json.loads((OUT / "dashboard_data" / "keywords_schema.json").read_text())
    names = labels(schema)
    parent = {
        gid: g.get("parent")
        for h in schema["headings"].values()
        for gid, g in h["groups"].items()
    }

    def ancestors(g):
        out = set()
        while parent.get(g):
            g = parent[g]
            out.add(g)
        return out

    heading = {gid: hid for hid, h in schema["headings"].items() for gid in h["groups"]}

    def related(a, b):
        return a in ancestors(b) or b in ancestors(a)

    def P_(g):
        return pretty(g, names)

    paths = sorted((OUT / args.region).glob("*/*/daily/pooled_daily.parquet"))
    dirs = {p.parents[1].name: p.parents[1] for p in paths}
    subs = {p.parents[1].name: p.parents[2].name for p in paths}
    countries = list(dirs)
    print(f"{len(countries)} countries with daily history")

    eps, res, breadths = [], {}, {}
    for name, cdir in dirs.items():
        w = weekly(cdir)
        ep, breadth = episodes(name, subs[name], w)
        eps.append(ep)
        breadths[name] = breadth
        R = residuals(w)
        if R.shape[1] >= 2:
            res[name] = R
    ep = pd.concat(eps, ignore_index=True)
    clean = ep[(ep["shape"] != "level shift") & ~ep.broad]
    nar = narratives(clean)
    pairs = recurring_pairs(nar, related)
    pairs["cross_heading"] = [
        heading.get(a) != heading.get(b) for a, b in zip(pairs.a, pairs.b)
    ]
    broad_weeks = int(sum((b > BROAD).sum() for b in breadths.values()))
    print(
        f"bursts: {len(ep):,} episodes, {(ep['shape'] == 'level shift').sum():,} level shifts, "
        f"{int(ep.broad.sum()):,} in broad weeks; {len(nar):,} narrative episodes, "
        f"{(nar.n_groups >= 2).sum():,} with 2+ groups; {len(pairs)} recurring pairs"
    )

    items = sorted(set().union(*[set(R.columns) for R in res.values()]))
    edges, bund, null = bundles(res, items, related, args.draws)
    edges["cross_heading"] = [
        heading.get(a) != heading.get(b) for a, b in zip(edges.a, edges.b)
    ]
    print(
        f"bundles: {len(items)} groups, {len(edges):,} pairs, {int(edges.fdr.sum()):,} pass FDR, "
        f"{int((edges.fdr & (edges.partial_r.abs() > 0)).sum()):,} direct; {len(bund)} bundles"
    )
    sub_names = sorted(set(subs.values()))
    strength = []
    for b in bund.itertuples():
        row = {"bundle": b.bundle}
        for s in sub_names:
            v = [bundle_strength(res[c], b.members) for c in res if subs[c] == s]
            row[s] = np.nanmean(v) if np.isfinite(v).any() else np.nan
        for c in res:
            row[c] = bundle_strength(res[c], b.members)
        for y in range(2016, date.today().year + 1):
            v = [bundle_strength(R[R.index.year == y], b.members) for R in res.values()]
            row[str(y)] = np.nanmean(v) if np.isfinite(v).any() else np.nan
        strength.append(row)
    strength = pd.DataFrame(strength)

    weeks = pd.date_range(clean.peak.min(), clean.peak.max(), freq="W-SUN")
    groups = sorted(clean.group.unique())
    Pk = peak_panel(clean, weeks, groups, countries)
    events = regional_events(Pk, weeks, groups, countries, subs)
    lift, obs, exp = coburst_lift(Pk, args.draws)
    same = np.array([[subs[a] == subs[b] for b in countries] for a in countries])
    off = ~np.eye(len(countries), dtype=bool)
    within = obs[same & off].sum() / exp[same & off].sum()
    between = obs[~same].sum() / exp[~same].sum()
    var = variance_shares(res, subs)
    n_ev = int(events.fdr.sum()) if len(events) else 0
    print(
        f"spread: {len(events)} regional bursts, {n_ev} pass FDR "
        f"({int(events[events.fdr].after_allafrica.sum()) if n_ev else 0} after AllAfrica start, "
        f"{int(events[events.fdr].calendar.sum()) if n_ev else 0} recur yearly); "
        f"co-burst lift within subregion {within:.2f}, between {between:.2f}; "
        f"median region share {var.region_share.median():.1%}, "
        f"subregion extra {var.subregion_extra.median():.1%}"
    )

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stem = REPORT_DIR / f"{date.today():%Y-%m-%d}-narratives-{args.region}"
    ep.to_csv(f"{stem}.episodes.csv", index=False)
    nar.assign(groups=nar.groups.map(";".join)).to_csv(
        f"{stem}.narratives.csv", index=False
    )
    pairs.to_csv(f"{stem}.pairs.csv", index=False)
    edges.to_csv(f"{stem}.edges.csv", index=False)
    bund.assign(members=bund.members.map(";".join)).to_csv(
        f"{stem}.bundles.csv", index=False
    )
    strength.to_csv(f"{stem}.bundle_strength.csv", index=False)
    events.assign(members=events.members.map(";".join)).to_csv(
        f"{stem}.regional.csv", index=False
    )
    pd.DataFrame(lift, index=countries, columns=countries).to_csv(f"{stem}.lift.csv")
    var.to_csv(f"{stem}.variance.csv", index=False)

    def glist(gs, k=4):
        return ", ".join(P_(g)[:30] for g in gs[:k]) + (
            f" +{len(gs) - k}" if len(gs) > k else ""
        )

    shapes = clean["shape"].value_counts()
    with PdfPages(f"{stem}.pdf") as pdf:
        text_page(
            pdf,
            f"Narratives: {args.region.upper()}",
            f"""Data: daily-history build, {len(countries)} countries (Mac), Monday-Sunday weeks,
same masking as weekly.py. Unit: groups ({len(groups)} with bursts).

1. BURSTS
A group bursts when its weekly count is >= {BURST_RATIO}x expected from its
share over the previous {BASE_WEEKS} weeks, >= {BURST_MIN} articles, Poisson p < {BURST_P:g}.
Episodes:                          {len(ep):,}
  level shifts (dropped):          {(ep["shape"] == "level shift").sum():,}
  in broad weeks (dropped):        {int(ep.broad.sum()):,} ({broad_weeks} country-weeks with
                                   > {BROAD:.0%} of groups bursting)
Kept: {len(clean):,} = {", ".join(f"{k} {v:,}" for k, v in shapes.items())}
Median decay: {clean.decay.median():.0f} week(s) to half the peak excess.
Narrative episodes (peaks within {WINDOW} wk): {len(nar):,}, {(nar.n_groups >= 2).sum():,} with 2+ groups.
Recurring pairs (>= {PAIR_MIN} episodes): {len(pairs)}.

2. SAME-WEEK BUNDLES
High-passed log shares ({HP_WEEKS}-week centred mean out), log articles,
log sources and the country's first {COMMON_PCS} principal component(s) removed. Pooled same-week r over >= {MIN_COUNTRIES} countries,
p from {args.draws} sets of shifted copies, BH {FDR:.0%}. Parent-child pairs excluded.
Groups: {len(items)}   pairs: {len(edges):,}   pass FDR: {int(edges.fdr.sum()):,}
Direct (graphical lasso, alpha {GLASSO_ALPHA}): {int((edges.fdr & (edges.partial_r.abs() > 0)).sum()):,}
Bundles (average linkage, mean r >= {CUT_R}, 3+ groups): {len(bund)}

3. SPREAD
Regional bursts (>= {SYNC_MIN} countries peak within 1 week): {len(events)},
  pass FDR: {n_ev}, of which after the AllAfrica start ({ALLAFRICA_START:%Y-%m-%d}): {int(events[events.fdr].after_allafrica.sum()) if n_ev else 0}
  recur at the same time of year (calendar days, summits): {int(events[events.fdr].calendar.sum()) if n_ev else 0}
Co-burst lift (same group, peaks within 1 week; 1 = chance):
  same subregion {within:.2f}   different subregion {between:.2f}
Variance of each group's weekly residual explained (median over groups):
  SSA mean {var.region_share.median():.1%}, subregion mean adds {var.subregion_extra.median():.1%}
""",
            size=8.5,
        )

        top = nar[nar.n_groups >= 2].sort_values("excess", ascending=False).head(30)
        table_page(
            pdf,
            "Biggest narrative episodes (2+ groups bursting together)",
            pd.DataFrame(
                {
                    "country": top.country,
                    "week of": top.week.dt.strftime("%Y-%m-%d"),
                    "groups": top.n_groups,
                    "extra articles": top.excess.round().astype(int),
                    "top groups": top.groups.map(glist),
                }
            ),
            "Extra articles = sum over groups and weeks of count above expected. Read the week's headlines to name the story.",
        )

        recent = nar[(nar.n_groups >= 2) & (nar.week >= "2025-01-01")]
        top = recent.sort_values("excess", ascending=False).head(30)
        table_page(
            pdf,
            "Biggest narrative episodes since 2025",
            pd.DataFrame(
                {
                    "country": top.country,
                    "week of": top.week.dt.strftime("%Y-%m-%d"),
                    "groups": top.n_groups,
                    "extra articles": top.excess.round().astype(int),
                    "top groups": top.groups.map(glist),
                }
            ),
        )

        top = pairs.head(30)
        table_page(
            pdf,
            "Groups that burst together again and again",
            pd.DataFrame(
                {
                    "group A": top.a.map(P_),
                    "group B": top.b.map(P_),
                    "episodes": top.episodes,
                    "countries": top.countries,
                    "lift": top.lift.round(1),
                }
            ),
            "Lift = how many times more often they burst together than if independent.",
        )

        top = pairs[pairs.cross_heading].head(30)
        table_page(
            pdf,
            "Recurring burst pairs across different headings",
            pd.DataFrame(
                {
                    "group A": top.a.map(P_),
                    "heading A": top.a.map(heading),
                    "group B": top.b.map(P_),
                    "heading B": top.b.map(heading),
                    "episodes": top.episodes,
                    "countries": top.countries,
                    "lift": top.lift.round(1),
                }
            ),
            "Pairs inside one heading often share keywords or articles; links across headings are closer to a story.",
        )

        top = (
            edges[edges.fdr & edges.cross_heading]
            .sort_values("r", ascending=False)
            .head(30)
        )
        table_page(
            pdf,
            "Strongest same-week links across different headings",
            pd.DataFrame(
                {
                    "group A": top.a.map(P_),
                    "heading A": top.a.map(heading),
                    "group B": top.b.map(P_),
                    "heading B": top.b.map(heading),
                    "pooled r": top.r.round(3),
                    "partial r": top.partial_r.round(3),
                    "countries": top.countries,
                }
            ),
            "Partial r (graphical lasso) 0 = the link runs through other groups.",
        )

        table_page(
            pdf,
            "Same-week bundles (pooled over countries)",
            pd.DataFrame(
                {
                    "bundle": bund.bundle,
                    "size": bund["size"],
                    "mean r": bund.mean_r.round(2),
                    "members": bund.members.map(lambda m: glist(m, 6)),
                }
            ).head(40),
            "Members ordered by how connected they are inside the bundle.",
        )

        if len(strength):
            k = min(len(strength), 40)
            bl = [f"{b} {glist(m, 2)}" for b, m in zip(bund.bundle, bund.members)][:k]
            yrs = [c for c in strength.columns if c.isdigit()]
            heat(
                pdf,
                "Bundle strength by subregion and year (mean within-bundle r)",
                strength[sub_names + yrs].head(k).to_numpy(dtype=float),
                bl,
                [s.replace("_", " ") for s in sub_names] + yrs,
                cmap="magma",
                vmin=0,
            )
            order = sorted(res, key=lambda c: (subs[c], c))
            heat(
                pdf,
                "Bundle strength by country",
                strength[order].head(k).to_numpy(dtype=float),
                bl,
                order,
                cmap="magma",
                vmin=0,
            )

        sig = events[events.fdr] if len(events) else events
        shown = sig if len(sig) else events
        top = shown.head(30)
        if len(top):
            table_page(
                pdf,
                "Regional bursts (same group peaking in several countries at once)"
                + ("" if len(sig) else ": none pass FDR"),
                pd.DataFrame(
                    {
                        "group": top.group.map(P_),
                        "week of": top.week.dt.strftime("%Y-%m-%d"),
                        "countries": top.countries,
                        "subregions": top.subregions,
                        "p": top.p.map(lambda v: f"{v:.2g}"),
                        "yearly": top.calendar,
                        "first movers first": top.members.map(
                            lambda m: ", ".join(m[:6]) + (" ..." if len(m) > 6 else "")
                        ),
                    }
                ),
                "Countries listed in the order their peak arrived.",
            )

        order = sorted(
            range(len(countries)), key=lambda i: (subs[countries[i]], countries[i])
        )
        heat(
            pdf,
            "Co-burst lift between countries (same group, peaks within 1 week; 1 = chance)",
            lift[np.ix_(order, order)],
            [countries[i] for i in order],
            [countries[i] for i in order],
            cmap="RdBu_r",
            vmin=0,
            vmax=2,
            note="Ordered by subregion.",
        )

        vt = var.sort_values("region_share", ascending=False).head(25)
        vs = var.sort_values("subregion_extra", ascending=False).head(25)
        table_page(
            pdf,
            "Most region-wide and most subregional groups",
            pd.DataFrame(
                {
                    "region-wide group": vt.group.map(P_).to_numpy(),
                    "SSA share": vt.region_share.map(lambda v: f"{v:.1%}").to_numpy(),
                    "subregional group": vs.group.map(P_).to_numpy(),
                    "subregion extra": vs.subregion_extra.map(
                        lambda v: f"{v:.1%}"
                    ).to_numpy(),
                }
            ),
            "Share of a country's weekly residual explained by the other countries' mean (SSA), and extra from its subregion.",
        )
    print(f"wrote {stem}.pdf")


if __name__ == "__main__":
    main()
