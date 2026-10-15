"""Themes: groups of concepts whose weekly news swings move together.

A fixed set of themes for a region, one theme per concept, found by rules
only (no human or model review):

1. Swing, per country and concept: log(1 + weekly Baker index) minus its
   trailing ``SWING``-week mean, less that week's mean swing over all
   groups (news-wide moves). Concepts mentioned in fewer than ``DENSE`` of
   the weeks are left out of that country.
2. Link of a pair in a country: the largest correlation of the two swings
   at lags -``MAX_LAG``..``MAX_LAG`` weeks (rain -> cholera takes weeks).
3. Pooled link: mean Fisher z over the countries where both concepts are
   dense, at least ``MIN_COUNTRIES`` of them, positive in at least
   ``AGREE`` of them.
4. Null: the same statistic on timing-scrambled copies (each series
   circularly shifted by its own random offset), pooled over the same
   number of countries. A link is kept at Benjamini-Hochberg ``FDR``.
5. Mechanical links dropped: a pair where a form of one concept contains a
   form of the other ("flash flood" contains "flood") counts the same
   words twice.
   Links are reported less the null's mean (the max over lags is positive
   by chance alone, more so on fewer weeks).
6. Themes: average-linkage clustering on 1 - pooled r (r = 0 for pairs not
   kept), cut where the mean link between two clusters falls below the
   weakest kept link. Themes of fewer than ``MIN_SIZE`` concepts are
   dropped.
7. Members: each must track the rest of its theme (rule 9's test against
   the other members, in the full run and each of the four halves below);
   the weakest failing one is dropped until all pass.
   Stability: the pooled links of each half of the period and of each half
   of the region's subregions (alphabetical: central + east Africa, southern
   + west for SSA), no threshold (halves have too little data to pass it).
   A theme is kept when, in each of the four, its mean member link beats the
   ``STABLE`` quantile of the mean link of ``DRAWS`` random concept sets of
   its size.
8. Name: the labels of its two most central members (largest sum of links
   to the rest of the theme).
9. Attach: an item in no theme joins the stable theme it tracks as a whole:
   its mean link to the members is in the top ``1 - ATTACH`` of all items,
   in the full run and in each of the four halves (one theme: its strongest). A
   single pair rarely passes step 4; a mean over members has more power.

10. Broad: a stable theme whose members are mentioned in more than
    ``BROAD`` of the region's articles in a usual period (the 12 complete
    months before this one; a random ``SHARE_RATE`` of them, matched as the
    build does) is flagged ``broad`` and left out of the dashboard: it spans
    everyday words, not a story. A usual period, so a theme that is big
    because of this month's news is not dropped; its members stay as topics.

``--level group`` runs the same rules on groups (a group's series counts
the concepts of its tree; a group and its subgroup share forms, so the
mechanical rule drops that pair) and lists the concepts the themes cover.

Reads every country's ``weekly/baker.parquet``. Writes
``outputs/text/<region>/themes_<level>.json``.

Run: python src/text/analysis/explorations/themes.py [--region ssa] [--level group]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

from lead_lag import OUT, bh_reject

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from src.text.analysis.utils import load_concept_catalog  # noqa: E402

START, END = "2019-01-06", "2026-10-11"
SWING = 13
DENSE = 0.02
MAX_LAG = 2
MIN_COUNTRIES = 3
AGREE = 0.6
SHIFTS = 10
FDR = 0.01
MIN_SIZE = 3
STABLE = 0.99
DRAWS = 1000
ATTACH = 0.99
CHECKS = ("h1", "h2", "g1", "g2")  # time halves, subregion halves
SEED = 0
BROAD = 0.2  # share of a usual period's articles
SHARE_RATE = 0.03  # articles sampled for that share


def swings(path: Path, start: str, end: str, level: str) -> pd.DataFrame:
    """Standardized swings (weeks x dense concepts or groups) of one country."""
    Z = pd.read_parquet(path)
    Z = Z[Z.index <= end]
    X = np.log1p(Z)
    X = (X - X.rolling(SWING).mean().shift(1)).loc[start:end]
    groups = X[[c for c in X if c.startswith("group_")]]
    cols = [c for c in X if c.startswith(f"{level}_")]
    seen = (Z.loc[start:end, cols] > 0).mean()
    X = X[cols].sub(groups.mean(axis=1), axis=0)
    X = X.loc[:, (seen >= DENSE).to_numpy() & (X.std() > 0).to_numpy()]
    X.columns = X.columns.str.removeprefix(f"{level}_")
    return ((X - X.mean()) / X.std()).fillna(0)


def lag_max(R: np.ndarray) -> np.ndarray:
    """Per pair, the largest correlation over lags -MAX_LAG..MAX_LAG."""
    n = len(R)
    S = R.T @ R / n
    for lag in range(1, MAX_LAG + 1):
        C = R[:-lag].T @ R[lag:] / (n - lag)
        S = np.maximum(S, np.maximum(C, C.T))
    return S


def shuffled(R: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    n = len(R)
    off = rng.integers(MAX_LAG * 2, n - MAX_LAG * 2, R.shape[1])
    idx = (np.arange(n)[:, None] - off[None, :]) % n
    return np.take_along_axis(R, idx, axis=0)


def pooled(frames: dict, concepts: list[str], rng) -> tuple:
    """Pooled Fisher z, country counts, sign agreement, and the null's pooled z."""
    k = len(concepts)
    pos = {c: i for i, c in enumerate(concepts)}
    zsum, zn, npos = np.zeros((k, k)), np.zeros((k, k)), np.zeros((k, k))
    nsum = np.zeros((SHIFTS, k, k))
    for X in frames.values():
        ix = np.array([pos[c] for c in X.columns])
        R = X.to_numpy()
        z = np.arctanh(np.clip(lag_max(R), -0.999, 0.999))
        sub = np.ix_(ix, ix)
        zsum[sub] += z
        zn[sub] += 1
        npos[sub] += z > 0
        for s in range(SHIFTS):
            nz = np.arctanh(np.clip(lag_max(shuffled(R, rng)), -0.999, 0.999))
            nsum[s][sub] += nz
    with np.errstate(invalid="ignore", divide="ignore"):
        return zsum / zn, zn, npos / zn, nsum / zn


def contains(forms: dict) -> callable:
    """A pair is mechanical when a form of one is a run of words in a form of the other."""
    words = {
        c: [tuple(re.findall(r"\w+", x.lower())) for x in fs] for c, fs in forms.items()
    }
    grams = {
        c: {w[i:j] for w in ws for i in range(len(w)) for j in range(i + 1, len(w) + 1)}
        for c, ws in words.items()
    }

    def overlap(a: str, b: str) -> bool:
        return bool(set(words[a]) & grams[b]) or bool(set(words[b]) & grams[a])

    return overlap


def links(frames: dict, overlap, rng) -> tuple[pd.DataFrame, float, pd.DataFrame]:
    """Kept pooled links (r; 0 when not kept), the weakest, and every pooled r."""
    concepts = sorted(set().union(*[X.columns for X in frames.values()]))
    z, n, agree, null = pooled(frames, concepts, rng)
    iu = np.triu_indices(len(concepts), 1)
    ok = n[iu] >= MIN_COUNTRIES
    obs, cnt = z[iu][ok], n[iu][ok]
    p = np.ones(len(obs))
    for m in np.unique(cnt):  # the null pooled over the same number of countries
        nul = np.sort(np.concatenate([s[iu][ok][cnt == m] for s in null]))
        at = cnt == m
        p[at] = (1 + len(nul) - np.searchsorted(nul, obs[at], side="left")) / (
            1 + len(nul)
        )
    keep = bh_reject(p, FDR) & (agree[iu][ok] >= AGREE) & (obs > 0)
    rows, cols = iu[0][ok][keep], iu[1][ok][keep]
    keep_mech = np.array(
        [not overlap(concepts[i], concepts[j]) for i, j in zip(rows, cols)], dtype=bool
    )
    print(
        f"  pairs {ok.sum():,}, significant {keep.sum():,}, "
        f"mechanical {int((~keep_mech).sum()) if len(keep_mech) else 0}"
    )
    rows, cols = rows[keep_mech], cols[keep_mech]
    L = np.zeros((len(concepts), len(concepts)))
    with warnings.catch_warnings():  # pairs in no country: all-NaN null
        warnings.simplefilter("ignore", RuntimeWarning)
        mean_null = np.nanmean(null, axis=0)
    # less what chance alone gives (the max over lags is positive by chance)
    zc = np.where(n >= MIN_COUNTRIES, z - mean_null, np.nan)
    L[rows, cols] = L[cols, rows] = np.tanh(zc[rows, cols])
    weakest = float(L[rows, cols].min()) if len(rows) else 1.0
    used = L.any(axis=0)
    names = [c for c, u in zip(concepts, used) if u]
    raw = pd.DataFrame(np.tanh(zc), index=concepts, columns=concepts)
    kept = pd.DataFrame(L[np.ix_(used, used)], index=names, columns=names)
    return kept, weakest, raw


def clusters(L: pd.DataFrame, cut: float) -> dict[str, int]:
    """Average-linkage themes on 1 - r, cut at mean link ``cut``."""
    if len(L) < 2:
        return {}
    D = 1 - L.to_numpy()
    np.fill_diagonal(D, 0)
    tree = linkage(squareform(D, checks=False), method="average")
    lab = fcluster(tree, 1 - cut, criterion="distance")
    return dict(zip(L.index, lab))


def themes_of(frames: dict, overlap, rng) -> tuple:
    L, weakest, raw = links(frames, overlap, rng)
    lab = clusters(L, weakest)
    out = {}
    for c, k in lab.items():
        out.setdefault(k, []).append(c)
    return {k: v for k, v in out.items() if len(v) >= MIN_SIZE}, L, weakest, raw


def mean_link(R: pd.DataFrame, members: list[str]) -> float:
    """Mean pooled r over member pairs (pairs pooled over too few countries skipped)."""
    S = R.reindex(index=members, columns=members).to_numpy()
    v = S[np.triu_indices(len(members), 1)]
    v = v[np.isfinite(v)]
    return float(v.mean()) if len(v) else float("nan")


def chance(R: pd.DataFrame, m: int, rng) -> float:
    """The STABLE quantile of the mean link of DRAWS random sets of m concepts."""
    names = list(R.index)
    draws = [
        mean_link(R, list(rng.choice(names, m, replace=False))) for _ in range(DRAWS)
    ]
    return float(np.nanquantile(draws, STABLE))


def tracks(R: dict, c: str, others: list[str]) -> bool:
    """c's mean link to ``others`` is in the top 1 - ATTACH of all items, in every run."""
    for M in R.values():
        v = M.reindex(columns=others).mean(axis=1).drop(others, errors="ignore")
        if not (c in v and v[c] > v.quantile(ATTACH)):
            return False
    return True


def prune(ms: list[str], R: dict) -> list[str]:
    """Drop, weakest first, members that do not track the rest (rule 7)."""
    ms = list(ms)
    while len(ms) >= MIN_SIZE:
        bad = [c for c in ms if not tracks(R, c, [m for m in ms if m != c])]
        if not bad:
            break
        full = R["full"]
        ms.remove(min(bad, key=lambda c: full.loc[c, [m for m in ms if m != c]].mean()))
    return ms


def attach(stable: list, R: dict, overlap, label: dict, tree: dict) -> None:
    """Add the items that track a stable theme as a whole (rule 9), in place."""
    taken = {m for t in stable for m in t["members"]}
    best = {}
    for k, t in enumerate(stable):
        ms = t["members"]
        ok, full = None, None
        for name, M in R.items():
            v = M.reindex(columns=ms).mean(axis=1).drop(ms, errors="ignore")
            hit = v > v.quantile(ATTACH)
            ok = hit if ok is None else ok & hit.reindex(ok.index, fill_value=False)
            if name == "full":
                full = v
        for c in ok.index[ok.to_numpy()]:
            if c in taken or any(overlap(c, m) for m in ms):
                continue
            if c not in best or full[c] > best[c][1]:
                best[c] = (k, float(full[c]))
    for t in stable:
        t["attached"] = []
    for c, (k, v) in sorted(best.items(), key=lambda x: -x[1][1]):
        stable[k]["attached"].append([c, label[c], round(v, 3)])
        stable[k]["concepts"] = sorted(set(stable[k]["concepts"]) | tree[c])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--region", default="ssa")
    ap.add_argument("--level", choices=["concept", "group"], default="concept")
    args = ap.parse_args()

    cat = load_concept_catalog()
    label = {c: v["label"] for c, v in cat["concepts"].items()}
    group = {c: v["group"] for c, v in cat["concepts"].items()}
    forms = {  # a form is a string or {"prefix": str}
        c: [
            f["prefix"] if isinstance(f, dict) else f
            for fs in v["forms"].values()
            for f in fs
        ]
        for c, v in cat["concepts"].items()
    }
    head = {g: v["heading"] for g, v in cat["groups"].items()}
    hlabel = {h: v["label"] for h, v in cat["headings"].items()}
    # A group's series counts its subgroups' concepts too (its tree).
    tree = {
        g: {
            c
            for c, gc in group.items()
            if gc == g or cat["groups"][gc].get("parent") == g
        }
        for g in cat["groups"]
    }
    if args.level == "group":
        group = {g: g for g in cat["groups"]}  # an item's own group, for its heading
        forms = {g: [f for c in cs for f in forms[c]] for g, cs in tree.items()}
        label = {g: v["label"] for g, v in cat["groups"].items()}
    else:
        tree = {c: {c} for c in label}
    overlap = contains(forms)

    paths = sorted((OUT / args.region).glob("*/*/weekly/baker.parquet"))
    paths = [p for p in paths if p.parents[1].name != "_aggregate"]
    mid = pd.Timestamp(START) + (pd.Timestamp(END) - pd.Timestamp(START)) / 2
    halves = [
        (START, f"{mid:%Y-%m-%d}"),
        (f"{mid + pd.Timedelta(days=7):%Y-%m-%d}", END),
    ]
    rng = np.random.default_rng(SEED)

    runs = {}
    subs = sorted({p.parents[2].name for p in paths})
    sides = [set(subs[: len(subs) // 2]), set(subs[len(subs) // 2 :])]
    checks = [
        ("full", START, END, None),
        ("h1", *halves[0], None),
        ("h2", *halves[1], None),
    ]
    checks += [(f"g{k + 1}", START, END, side) for k, side in enumerate(sides)]
    for name, a, b, side in checks:
        frames = {}
        for p in paths:
            if side and p.parents[2].name not in side:
                continue
            X = swings(p, a, b, args.level)
            if X.shape[1] >= 2:
                frames[p.parents[1].name] = X
        if side:
            a = "+".join(sorted(side))
        print(f"{name} {a}..{b}: {len(frames)} countries")
        if name == "full":
            runs[name] = themes_of(frames, overlap, rng)
            print(
                f"  weakest kept link r = {runs[name][2]:.3f}, themes {len(runs[name][0])}"
            )
        else:
            runs[name] = links(frames, overlap, rng)[2]

    th, L, weakest, _ = runs["full"]
    R = {"full": runs["full"][3], **{h: runs[h] for h in CHECKS}}
    out = []
    for ms in th.values():
        ms = prune(ms, R)
        if len(ms) < MIN_SIZE:
            continue
        S = L.loc[ms, ms]
        central = S.sum().sort_values(ascending=False)
        iu = np.triu_indices(len(ms), 1)
        stab = [mean_link(runs[h], ms) for h in CHECKS]
        bars = [chance(runs[h], len(ms), rng) for h in CHECKS]
        out.append(
            {
                "name": " / ".join(label[c] for c in central.index[:2]),
                "members": list(central.index),
                "concepts": sorted(set().union(*[tree[m] for m in ms])),
                "labels": [label[c] for c in central.index],
                "headings": sorted({hlabel[head[group[c]]] for c in ms}),
                "mean_r": round(float(S.to_numpy()[iu].mean()), 3),
                "stability": [round(x, 3) for x in stab],
                "chance": [round(x, 3) for x in bars],
                "stable": bool(all(x > b for x, b in zip(stab, bars))),
            }
        )
    out.sort(key=lambda t: (not t["stable"], -len(t["members"])))
    attach(
        [t for t in out if t["stable"]],
        {"full": runs["full"][3], **{h: runs[h] for h in CHECKS}},
        overlap,
        label,
        tree,
    )
    from overview import article_hits  # the build's matcher, on article bodies

    this = pd.Timestamp.today().to_period("M")
    usual = ((this - 12).to_timestamp(), this.to_timestamp() - pd.Timedelta(days=1))
    hits = article_hits(args.region, *usual, rate=SHARE_RATE)
    arts = [h for hs in hits.values() for h in hs]
    for t in out:
        if t["stable"]:
            m = set(t["members"])
            t["share"] = round(sum(1 for h in arts if h & m) / len(arts), 3)
            t["broad"] = t["share"] > BROAD
    print(f"broad: {len(arts)} articles sampled, {usual[0]:%Y-%m}..{usual[1]:%Y-%m}")
    path = OUT / args.region / f"themes_{args.level}.json"
    path.write_text(
        json.dumps(
            {
                "region": args.region,
                "level": args.level,
                "period": [START, END],
                "weakest_link": weakest,
                "broad": {"share": BROAD, "period": [f"{d:%Y-%m-%d}" for d in usual]},
                "themes": out,
            },
            indent=1,
            ensure_ascii=False,
        )
    )
    stable = [t for t in out if t["stable"]]
    covered = set().union(*[t["concepts"] for t in stable]) if stable else set()
    core = set().union(*[tree[m] for t in stable for m in t["members"]])
    print(
        f"{len(out)} themes, {len(stable)} stable, {len(core)} concepts as members,"
        f" {len(covered)} with attached; wrote {path}"
    )
    for t in stable:
        print(
            f"- {t['name']} ({len(t['members'])}, r {t['mean_r']}, checks {t['stability']} vs {t['chance']}, "
            f"{len(t['headings'])} headings, share {t['share']:.0%}{' BROAD' if t['broad'] else ''}): {', '.join(t['labels'][:8])}"
            f" + {len(t['attached'])} attached: {', '.join(x[1] for x in t['attached'][:6])}"
        )


if __name__ == "__main__":
    main()
