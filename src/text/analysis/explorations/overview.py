"""Overview data for the dashboard's first tab: subtopic bursts this week.

Per unit (region, subregions, countries), the subtopics (groups) bursting
this week, with:

- Burst flag: the rule of ``narratives.py`` per country (pooled weekly counts,
  >= 2.5x expected from the trailing 26-week share, >= 5 articles, Poisson
  p < 1e-4). A region or subregion row is a group bursting in >= 1 of its
  countries.
- Ratio vs usual: the weekly Baker index (``baker.index``, weighted: each
  panel source's share of articles mentioning it over that share's std
  across the 2024 weeks, averaged with weights = the source's share of the
  week's articles among the sources entering it; 100 = the 2024 weeks'
  mean; regions and subregions combine their countries as Baker's European
  EPU, equal weights). A source enters a group or concept only with >=
  ``MIN_BASE`` articles on it in 2024: a source that almost never covered it
  has a std near 0 and its next few articles would swamp the mean. Ratio =
  index this week / its mean over a comparison period (2024, the 52, 26 or
  8 weeks before).
- N = articles mentioning the group this week. The dashboard ranks by
  N - N / ratio (articles above a usual week).
- Badge: new, peaked k weeks ago, k weeks rising, k-th week; fading rows
  (stopped bursting in the last ``FADE`` weeks) are listed apart.
- Persistence: complete months in a row (ending last month) where the
  monthly Baker index is above ``ELEVATED`` times its 2024 mean. A group
  elevated for ``MIN_MONTHS`` months with >= ``BURST_MIN`` articles this week
  is listed even when not bursting (a long crisis stops bursting once it is
  the usual).
- A group none of whose articles this week come from a panel source has no
  ratio (``u``): Baker leaves the other sources out.

Heartbeat (``beat`` per unit): the last ``BEAT_DAYS`` UTC days, ending
today, of daily articles and group counts (masked days null), each group's
usual weekly count per comparison period, and its importance in the last
``FADE`` + 1 weeks (bursting, persistent or both). The dashboard computes the
7-day states (Pressing, Came Back, Gone quiet, pace) from the browser clock.

Series (``s`` per unit), for every group listed in rows, fading or beat,
and for the cards:

- Chart (x 100, 2024 = 100 at each frequency): ``wk`` the weekly index
  (sigma and 100 from the 2024 weeks) for the last ``CHART_WEEKS`` weeks
  ending t0 = ``week``, the last complete week; ``mo`` the monthly index
  (sigma and 100 from the 2024 months) for the ``CHART_MONTHS`` months up to
  the last complete one; ``nw``, ``nm`` their articles (theme lines:
  mentions). The page draws their trailing means (3 months; 4, 3 or 2 weeks).
- ``hs``: the month of the latest week ending >= 4 weeks before t0 whose
  4-week mean of the weekly index is at or above the last 4 weeks' (null:
  none since 2015). The page's headline and ranking read the last 4 weeks'
  mean from ``wk`` (``q`` here, / 100: 2.3 reads "2.3x its 2024 level").
- ``nd``, ``ns``: articles (theme lines: mentions) and panel and other
  sources mentioning it in the last ``DAYS`` days. The page ranks by
  ``above``: (n - n/q) / sqrt(n/q), the index above usual in counting noise.
- ``tr``: 1 when the last week's weekly index is above its 4-week mean and
  each of the 3 weeks before it, -1 when below them. ``b``: bursting this
  week.
- ``w`` (region and subregions): the ``BY`` countries furthest above their
  2024 level on the same rule, [country, q, n].

Cards (``cards`` per unit): the top groups (no parent) with something listed
in their tree; ``kids`` their subgroups.

Themes (``outputs/text/<region>/themes_concept.json`` from ``themes.py``,
stable ones that are not broad): per unit, series and heartbeat inputs for each theme line
(``t:<k>``: the mean of its members' indices over their 2024 means, at each
frequency; summed member mentions) and member concept (``c:<id>``).

Stories (``dc`` per unit, every group and theme in ``s``): the
``TOP_CONCEPTS`` concepts of its tree with the most articles above their
usual week (past year) this week, as ids (``clabels``).

KPIs: ``kpi.total`` is every article in the database for the unit's
countries (``outputs/text/database_status/sources_<region>.csv``, written by
``src/text/status.py``).

Same articles (``co`` per unit): for each topic A (group or theme) with
>= ``BURST_MIN`` articles this week, the bigger topics B (more articles)
mentioned in >= ``CO_SHARE`` of A's articles, with lift (that share over
B's share of all the unit's articles) >= ``CO_LIFT``: Baker's category
indices count a category in the same articles the same way. The page folds
A into B's card. Matched with the build's keyword matcher (``annotate.py``)
on the bodies of this week's articles in ``data/text/<region>``.

Days with suspect source dumps are dropped from the counts as in
``weekly.py``. Reads each country's ``daily/`` files (a ``text build
--region <r> --daily-history``) and this week's articles. Writes
``outputs/text/<region>/overview.json``, read by ``small_dashboard_concepts.py``.

Run: python src/text/analysis/explorations/overview.py [--region ssa]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd

from lead_lag import OUT, ROOT

sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from src.text.analysis import annotate  # noqa: E402
from src.text.analysis.baker import combine, index, panel  # noqa: E402
from src.text.analysis.main import _source_language  # noqa: E402
from narratives import BURST_MIN, bursts  # noqa: E402
from weekly import MASK_SHARE, masked_days, weekly  # noqa: E402

BASE = ("2024-01-01", "2024-12-31")
PERIODS = ("2024", "52", "104")  # comparison windows: 2024, or weeks before this one
DAYS = 28  # the ranking's period (4 weeks), ending on the week's last day
MA = DAYS // 7  # weeks in the headline's mean of the weekly index
FADE = 3  # weeks a stopped burst stays listed as fading
TOP_CONCEPTS = 3
ELEVATED = 1.5  # x the 2024 level
MIN_MONTHS = 2  # complete months in a row for a group to count as persistent
MIN_BASE = 10  # 2024 articles on a topic for a source to enter its index
CO_SHARE = 0.5  # share of A's articles that mention B for A to fold into B
CO_LIFT = 4  # that share over B's share of all articles
BEAT_DAYS = 21  # 7-day window + the 14 days before it (Came Back)
HISTORY = 10  # 2024 articles for a group to "come back"
CHART_WEEKS = 30  # weekly points sent to the page (section 2 at most 22 + MA)
CHART_MONTHS = 52  # monthly points (section 1 at most 4 years + 3)
BY = 5  # countries per region card
WHERE_MIN = 5  # articles in the last DAYS days for a country to be listed


def last_week(today: date) -> pd.Timestamp:
    last = pd.Timestamp(today) - pd.Timedelta(days=1)
    return last - pd.Timedelta(days=(last.dayofweek + 1) % 7)  # back to Sunday


def week_end(d: pd.Series) -> pd.Series:
    return d + pd.to_timedelta((6 - d.dt.dayofweek) % 7, unit="D")


def country_numbers(
    cdir, weeks: pd.DatetimeIndex, days: pd.DatetimeIndex, axes: tuple
) -> dict:
    """Weekly and daily articles and term counts (periods x terms) for a country,
    each term's articles and sources in the last DAYS days, and its articles
    in the chart's calendar months (``chart_axes``).

    Daily values on masked days are NaN.
    """
    d = cdir / "daily"
    sources = pd.read_parquet(d / "sources_daily.parquet")
    bad = masked_days(sources)
    drop = set(bad[bad > MASK_SHARE].index)
    sources = sources[~sources.date.isin(drop)]
    A = (
        sources.groupby(week_end(sources.date))
        .A_total.sum()
        .reindex(weeks, fill_value=0)
    )
    t = pd.read_parquet(d / "sources_terms_daily.parquet")
    t = t[~t.date.isin(drop)]
    counts = (
        t.groupby([week_end(t.date), "term"], observed=True)["count"]
        .sum()
        .unstack(fill_value=0)
        .reindex(weeks, fill_value=0)
    )
    daily = (
        t[t.date.isin(days)]
        .groupby(["date", "term"], observed=True)["count"]
        .sum()
        .unstack(fill_value=0)
        .reindex(days, fill_value=0)
    )
    nm = (
        t[t.date >= axes[1][0]]
        .groupby([t.date.dt.to_period("M").dt.to_timestamp(), "term"], observed=True)[
            "count"
        ]
        .sum()
        .unstack(fill_value=0)
        .reindex(axes[1], fill_value=0)
    )
    for c in (counts, daily, nm):
        c.columns = c.columns.astype(str).str.replace(
            r"^(group|concept)_(.*)_A_count$", r"\2", regex=True
        )
    lw = t[(t.date > weeks[-1] - pd.Timedelta(days=DAYS)) & (t.date <= weeks[-1])]
    lw = lw.assign(
        term=lw.term.astype(str).str.replace(
            r"^(group|concept)_(.*)_A_count$", r"\2", regex=True
        )
    )
    nd = lw.groupby("term")["count"].sum()
    src = lw.groupby("term").source_key.agg(lambda x: set(x.astype(str)))
    dA = sources.groupby("date").A_total.sum().reindex(days, fill_value=0)
    masked = days.isin(list(drop))
    dA[masked] = np.nan
    daily[masked] = np.nan
    return {
        "articles": A,
        "counts": counts,
        "d_articles": dA,
        "d_counts": daily,
        "nd": nd,
        "nm": nm,
        "src": src.to_dict(),
    }


def add(parts: list[dict]) -> dict:
    out = parts[0]
    for p in parts[1:]:
        src = dict(out["src"])
        for g, v in p["src"].items():
            src[g] = src.get(g, set()) | v
        out = {k: out[k].add(p[k], fill_value=0) for k in out if k != "src"}
        out["src"] = src
    return out


def ratios(Z: pd.DataFrame, groups: list[str]) -> dict[str, list]:
    """Ratio of this week's Z to the mean Z of each comparison period."""
    Z = Z.reindex(columns=groups, fill_value=0)
    now, past = Z.iloc[-1], Z.iloc[:-1]
    means = [past.loc[BASE[0] : BASE[1]].mean()] + [
        past.iloc[-int(p) :].mean() for p in PERIODS[1:]
    ]
    out = {}
    for g in groups:
        r = [now[g] / m[g] if m[g] > 0 else np.nan for m in means]
        out[g] = [round(float(x), 2) if np.isfinite(x) else None for x in r]
    return out


def _terms(Z: pd.DataFrame) -> pd.DataFrame:
    Z.columns = Z.columns.astype(str).str.replace(
        r"^(group|concept)_(.*)_A_count$", r"\2", regex=True
    )
    return Z


def indices(cdir, weeks: pd.DatetimeIndex) -> tuple:
    """A country's weekly and monthly Baker index (periods x groups and
    concepts), each its own index: sigma and 100 from the 2024 weeks or
    months, the sources weighted by their articles (``baker.index``).

    Same panel and 2024 baseline as the build's ``weekly/baker.parquet``,
    from the raw daily files. Sources enter a term only with >= MIN_BASE
    articles on it over the baseline.
    """
    d = cdir / "daily"
    sources = pd.read_parquet(d / "sources_daily.parquet")
    terms = pd.read_parquet(d / "sources_terms_daily.parquet")
    P = panel(sources, *BASE)
    W, M = (
        _terms(
            index(
                sources, terms, P, f, *BASE, min_base_articles=MIN_BASE, weighted=True
            )
        )
        for f in ("W", "M")
    )
    return W.reindex(weeks), M


def week_hits(region: str, end: pd.Timestamp) -> dict[str, list[set]]:
    """Per country, the groups and concepts each article of the week ending
    ``end`` mentions (its body, as the build matches it; one set per article)."""
    return article_hits(region, end - pd.Timedelta(days=6), end)


def article_hits(
    region: str, start: pd.Timestamp, end: pd.Timestamp, rate: float = 1.0
) -> dict[str, list[set]]:
    """Per country, the groups and concepts each article dated ``start`` to
    ``end`` mentions; ``rate`` < 1 keeps a random share of the articles
    (seeded)."""
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.csv as pcsv

    lo, hi = f"{start:%Y-%m-%d}", f"{end:%Y-%m-%d}~"
    rng = np.random.default_rng(0)
    combos, out = {}, {}
    for f in sorted((ROOT / "data" / "text" / region).glob("*/*/*/news.csv")):
        lang = _source_language(f)
        lang = annotate.LANGUAGE_ALIASES.get(lang, lang)
        if lang not in combos:
            combos[lang] = annotate.build_combined_automaton(
                annotate.KeywordBundle.for_language(lang)
            )
        cols = ["date", "body", "url"]
        reader = pcsv.open_csv(
            f,
            convert_options=pcsv.ConvertOptions(
                include_columns=cols, column_types=dict.fromkeys(cols, pa.string())
            ),
            parse_options=pcsv.ParseOptions(newlines_in_values=True),
        )
        seen, hits = set(), out.setdefault(f.parent.parent.name, [])
        for b in reader:
            d = b.column("date")  # ISO dates; the few others are not parsed
            b = b.filter(pc.and_(pc.greater_equal(d, lo), pc.less(d, hi)))
            for date_, body, url in zip(*(b.column(c).to_pylist() for c in cols)):
                if body is None or (date_, body, url) in seen:
                    continue
                if rate < 1 and rng.random() >= rate:
                    continue
                seen.add((date_, body, url))
                cats = annotate._match_all_categories(
                    annotate._process_body(body), combos[lang]
                )
                hits.append(
                    {
                        c.split(":", 1)[1]
                        for c in cats
                        if c.startswith(("group:", "concept:"))
                    }
                )
    return out


def same_articles(hits: list[set], topics: dict[str, set]) -> dict:
    """Per topic A, the bigger topics B in >= CO_SHARE of A's articles with
    lift >= CO_LIFT, as [B, share, lift], best share first.

    ``topics``: a topic's ids (a group, or a theme's member concepts); an
    article mentions it when it mentions any of them.
    """
    keys = list(topics)
    H = np.array([[bool(h & topics[k]) for k in keys] for h in hits], dtype=float)
    if not len(H):
        return {}
    n = H.sum(axis=0)
    both = H.T @ H
    out = {}
    for i, a in enumerate(keys):
        if n[i] < BURST_MIN:
            continue
        share = both[i] / n[i]
        lift = share / (n / len(H))
        ok = (share >= CO_SHARE) & (lift >= CO_LIFT) & (n > n[i])
        js = sorted(np.flatnonzero(ok), key=lambda j: -share[j])
        if js:
            out[a] = [
                [keys[j], round(float(share[j]), 2), round(float(lift[j]), 1)]
                for j in js[:5]
            ]
    return out


def elevated_months(M: pd.DataFrame) -> pd.Series:
    """Complete months in a row, ending last month, with M above ELEVATED x 2024."""
    U = M.iloc[:-1].gt(100 * ELEVATED).to_numpy(dtype=bool)[::-1]
    run = np.where(U.all(axis=0), len(U), np.argmax(~U, axis=0))
    return pd.Series(run, index=M.columns)


def usual_articles(A: pd.Series) -> list[float]:
    past = A.iloc[:-1]
    return [round(float(past.loc[BASE[0] : BASE[1]].mean()), 1)] + [
        round(float(past.iloc[-int(p) :].mean()), 1) for p in PERIODS[1:]
    ]


def _num(x) -> float | None:
    return None if pd.isna(x) else round(float(x), 1)


def beat(num: dict, F: pd.DataFrame, M: pd.DataFrame, groups: set[str]) -> dict:
    """Heartbeat inputs of a unit: daily counts of the last BEAT_DAYS days.

    Groups listed: mentioned in those days or important (bursting or
    persistent; "bp" when both).
    """
    burst = set(F.columns[F.iloc[-1 - FADE :].any().to_numpy()])
    run = elevated_months(M)
    persistent = set(run.index[run >= MIN_MONTHS])
    D = num["d_counts"]
    mentioned = set(D.columns[D.fillna(0).sum() > 0])
    W = num["counts"]
    h2024 = W.loc[BASE[0] : BASE[1]].sum()
    out = {}
    for g in sorted((mentioned | burst | persistent) & groups):
        imp = ("b" if g in burst else "") + ("p" if g in persistent else "")
        d = D[g] if g in D else num["d_articles"] * 0  # zeros, masked days kept
        row = {
            "d": [None if pd.isna(x) else int(x) for x in d],
            "u": usual_articles(W[g]) if g in W else [0.0] * len(PERIODS),
        }
        if imp:
            row["i"] = imp
        if h2024.get(g, 0) >= HISTORY:
            row["h"] = 1
        out[g] = row
    return {
        "a": [_num(x) for x in num["d_articles"]],
        "ua": usual_articles(num["articles"]),
        "g": out,
    }


def above(q: float | None, n: int) -> float | None:
    """How far a topic's index sits above usual in counting noise: its n
    articles against the n / q a usual DAYS days would have, (n - n/q) /
    sqrt(n/q)."""
    if q is None or not q > 0 or not n:
        return None
    return (n - n / q) / np.sqrt(n / q)


def last4(W: pd.DataFrame) -> pd.Series:
    """The weekly index's mean over the last MA weeks (weeks with a value)."""
    return W.iloc[-MA:].mean()


def series(
    F: pd.DataFrame,
    W: pd.DataFrame,
    nd: pd.Series,
    src: dict,
    groups: list[str],
) -> dict:
    """Per group, from the weekly index: the month of the latest week ending
    >= MA weeks before the last whose MA-week mean is at or above the last
    MA weeks' (``hs``), the trend, its articles and sources in the last DAYS
    days and this week's burst flag."""
    burst = F.reindex(columns=groups, fill_value=False).iloc[-1]
    W = W.reindex(columns=groups)
    q, H = last4(W), W.rolling(MA, min_periods=1).mean().iloc[:-MA]
    out = {}
    for g in groups:
        h = H[g][H[g] >= q[g]] if pd.notna(q[g]) else H[g].iloc[:0]
        row = {
            "hs": f"{h.index[-1]:%Y-%m}" if len(h) else None,
            "nd": int(nd.get(g, 0)),
            "ns": len(src.get(g, ())),
        }
        w = W[g].iloc[-MA:]  # trend: the last week against the ones before
        if w.notna().all() and pd.notna(q[g]):
            if w.iloc[-1] > q[g] and w.iloc[-1] > w.iloc[:-1].max():
                row["tr"] = 1
            elif w.iloc[-1] < q[g] and w.iloc[-1] < w.iloc[:-1].min():
                row["tr"] = -1
        if burst[g]:
            row["b"] = 1
        out[g] = row
    return out


def chart_axes(t0: pd.Timestamp) -> tuple:
    """The chart's dates: the CHART_WEEKS weeks ending ``t0`` (the last
    complete week) and the CHART_MONTHS calendar months up to the last
    complete one."""
    weeks = pd.date_range(end=t0, periods=CHART_WEEKS, freq="W-SUN")
    last = (t0 + pd.Timedelta(days=1)).to_period("M") - 1
    months = pd.period_range(end=last, periods=CHART_MONTHS, freq="M").to_timestamp()
    return weeks, months


def chart(W, M, NW, NM, keys: list[str], axes: tuple) -> dict:
    """Per key, the chart's series on ``chart_axes``: ``wk`` the weekly and
    ``mo`` the monthly index (x 100), ``nw`` and ``nm`` their articles."""
    one = lambda x: [None if pd.isna(v) else round(float(v), 1) for v in x]  # noqa: E731
    ints = lambda x: [None if pd.isna(v) else int(round(v)) for v in x]  # noqa: E731
    out = {g: {} for g in keys}
    for k, Z, a, f in (
        ("wk", W, axes[0], one),
        ("mo", M, axes[1], one),
        ("nw", NW, axes[0], ints),
        ("nm", NM, axes[1], ints),
    ):
        Z = Z.reindex(index=a, columns=keys)
        for g in keys:
            out[g][k] = f(Z[g])
    return out


def where(g: str, members: list[str], CQ: dict, CN: dict) -> list:
    """The BY countries with >= WHERE_MIN articles furthest above their 2024
    level on g (``above`` of the last 4 weeks): [country, x 2024, articles]."""
    rows = []
    for c in members:
        q, n = CQ[c].get(g), int(CN[c].get(g, 0))
        q = None if q is None or pd.isna(q) else float(q)
        if n >= WHERE_MIN and (a := above(q, n)) is not None and a > 0:
            rows.append((a, c, round(q, 2), n))
    rows.sort(reverse=True)
    return [[c, q, n] for _, c, q, n in rows[:BY]]


def drivers(W: pd.DataFrame, tree: list[str]) -> list:
    """The TOP_CONCEPTS concepts with the most articles above usual this week."""
    W = W.reindex(columns=tree, fill_value=0)
    above = W.iloc[-1] - W.iloc[-53:-1].mean()
    above = above[above >= 1].sort_values(ascending=False).iloc[:TOP_CONCEPTS]
    return [[c, int(W[c].iloc[-1]), int(round(a))] for c, a in above.items()]


def theme_index(Zc: pd.DataFrame, themes: list) -> pd.DataFrame:
    """Theme lines ("t:<k>": mean of members' indices, each over its 2024
    mean, x 100) and member concepts ("c:<id>") of a concept index."""
    Z = {}
    for k, t in enumerate(themes):
        z = Zc.reindex(columns=t["members"])
        base = z.loc[BASE[0] : BASE[1]].mean()
        Z[f"t:{k}"] = (100 * z / base.where(base > 0)).mean(axis=1)
        Z.update({f"c:{c}": z[c] for c in t["members"]})
    return pd.DataFrame(Z)


def theme_nd(nd: pd.Series, themes: list) -> pd.Series:
    """Last DAYS days' mentions of each theme line (summed members) and member
    concept, keyed "t:<k>" and "c:<id>"."""
    t = pd.Series(
        {
            f"t:{k}": sum(nd.get(c, 0) for c in t["members"])
            for k, t in enumerate(themes)
        },
        dtype=float,
    )
    return pd.concat([t, nd.rename(lambda c: f"c:{c}")])


def theme_sources(src: dict, themes: list) -> dict:
    """Sources this week of each theme line (any member) and member concept."""
    out = {}
    for k, t in enumerate(themes):
        out[f"t:{k}"] = set().union(*(src.get(c, set()) for c in t["members"]))
        out.update({f"c:{c}": src.get(c, set()) for c in t["members"]})
    return out


def theme_frames(
    Zc: pd.DataFrame,
    W: pd.DataFrame,
    D: pd.DataFrame,
    F: pd.DataFrame,
    masked: pd.Series,
    themes: list,
) -> tuple:
    """A unit's theme lines ("t:<k>") and member concepts ("c:<id>").

    Index, weekly counts, daily counts (masked days NaN) and burst flags. A
    theme's index is the mean of its members' indices, each over its 2024
    mean (x 100); its counts are summed mentions (an article naming two
    members counts twice); it bursts when a member does.
    """
    Wo, Do, Fo = {}, {}, {}
    for k, t in enumerate(themes):
        ms = t["members"]
        Wo[f"t:{k}"] = W.reindex(columns=ms, fill_value=0).sum(axis=1)
        Do[f"t:{k}"] = D.reindex(columns=ms, fill_value=0).sum(axis=1)
        Fo[f"t:{k}"] = F.reindex(columns=ms, fill_value=False).any(axis=1)
        for c in ms:
            Wo[f"c:{c}"] = W[c] if c in W else pd.Series(0, index=W.index)
            Do[f"c:{c}"] = D[c] if c in D else pd.Series(0, index=D.index)
            Fo[f"c:{c}"] = F[c] if c in F else False
    D = pd.DataFrame(Do)
    D[masked.to_numpy()] = np.nan
    Z = theme_index(Zc, themes)
    return Z, pd.DataFrame(Wo), D, pd.DataFrame(Fo).astype(bool)


def badge(F: np.ndarray, N: np.ndarray) -> list:
    """Status of a group from its burst flags F and counts N (last = this week)."""
    if not F[-1]:
        k = int(np.flatnonzero(F[::-1])[0])
        return ["fade", k]
    back = np.flatnonzero(~F[::-1])
    run = int(back[0]) if len(back) else len(F)
    if run == 1:
        return ["new"]
    peak = int(np.argmax(N[-run:][::-1]))  # weeks ago; ties go to the latest
    if peak > 0:
        return ["peak", peak]
    up = np.flatnonzero(~(np.diff(N[-run:]) > 0)[::-1])
    rising = int(up[0]) if len(up) else run - 1
    return ["rise", rising] if rising >= 2 else ["wk", run]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--region", default="ssa")
    args = ap.parse_args()

    schema = json.loads((OUT / "dashboard_data" / "keywords_schema.json").read_text())
    parent, label, concepts, clabel, head = {}, {}, {}, {}, {}
    for hid, h in schema["headings"].items():
        for gid, g in h["groups"].items():
            parent[gid] = g.get("parent")
            head[gid] = hid
            label[gid] = f"{h['label']} · {g['label']}"
        for cid, c in h["concepts"].items():
            concepts.setdefault(c["group"], []).append(cid)
            clabel[cid] = c["label"]

    tops = [g for g in parent if not parent[g]]
    kids = {}
    for g, p in parent.items():
        if p:
            kids.setdefault(p, []).append(g)

    for c, gid in ((c, g) for g, cs in concepts.items() for c in cs):
        label[f"c:{c}"] = f"{label[gid].split(' · ')[0]} · {clabel[c]}"

    def ancestors(g):
        out = set()
        while parent.get(g):
            g = parent[g]
            out.add(g)
        return out

    last = last_week(date.today())
    weeks = pd.date_range("2015-01-04", last, freq="W-SUN")
    asof = datetime.now(timezone.utc)
    days = pd.date_range(end=pd.Timestamp(asof.date()), periods=BEAT_DAYS, freq="D")
    paths = sorted((OUT / args.region).glob("*/*/daily/sources_terms_daily.parquet"))
    dirs = {p.parents[1].name: p.parents[1] for p in paths}
    sub_of = {p.parents[1].name: p.parents[2].name for p in paths}
    print(f"{len(dirs)} countries, week ending {last:%Y-%m-%d}")

    tpath = OUT / args.region / "themes_concept.json"
    themes = (
        [
            t
            for t in json.loads(tpath.read_text())["themes"]
            if t["stable"] and not t.get("broad")
        ]
        if tpath.exists()
        else []
    )
    db = OUT / "database_status" / f"sources_{args.region}.csv"
    db = pd.read_csv(db) if db.exists() else None
    label.update({f"t:{k}": f"Theme · {t['name']}" for k, t in enumerate(themes)})
    nums, flags, Zc, cflags, Mc, CQ, CN = {}, {}, {}, {}, {}, {}, {}
    axes = chart_axes(last)  # t0 of the charts: the last complete week
    for name, cdir in dirs.items():
        nums[name] = country_numbers(cdir, weeks, days, axes)
        Zc[name], Mc[name] = indices(cdir, weeks)
        hit = bursts(weekly(cdir))[0]
        flags[name] = hit.reindex(weeks, fill_value=False).astype(bool)
        if themes:
            hit = bursts(weekly(cdir, "concept_"))[0]
            cflags[name] = hit.reindex(weeks, fill_value=False).astype(bool)
        # Where (region and subregions): each country's last 4 weeks.
        CQ[name] = (
            pd.concat(
                [last4(Zc[name])]
                + ([last4(theme_index(Zc[name], themes))] if themes else [])
            )
            / 100
        )
        CN[name] = pd.concat([nums[name]["nd"], theme_nd(nums[name]["nd"], themes)])

    subs = {}
    for c, s in sub_of.items():
        subs.setdefault(s, []).append(c)
    units = {"region": list(dirs)}
    units.update({f"subregion:{s}": cs for s, cs in sorted(subs.items())})
    units.update({c: [c] for c in sorted(dirs)})

    hits = week_hits(args.region, last)
    print(f"same articles: {sum(map(len, hits.values()))} articles this week")
    out_units = {}
    for u, members in units.items():
        num = nums[members[0]] if len(members) == 1 else add([nums[c] for c in members])
        F = pd.concat([flags[c] for c in members], axis=1).T.groupby(level=0).any().T
        bursting = {
            c: set(flags[c].columns[flags[c].iloc[-1].to_numpy()]) for c in members
        }
        Z = Zc[members[0]] if u in dirs else combine([Zc[c] for c in members], *BASE)[1]
        M = Mc[members[0]] if u in dirs else combine([Mc[c] for c in members], *BASE)[1]
        run = elevated_months(M)
        now = num["counts"].iloc[-1]
        persistent = [
            g
            for g in run.index[run >= MIN_MONTHS]
            if now.get(g, 0) >= BURST_MIN and g in label
        ]
        burst = list(F.columns[F.iloc[-1 - FADE :].any().to_numpy()])
        recent = burst + [g for g in persistent if g not in set(burst)]
        N = num["counts"].reindex(columns=recent, fill_value=0)
        rs = ratios(Z, recent)
        rows, fading = [], []
        for g in recent:
            b = badge(F[g].to_numpy(), N[g].to_numpy()) if g in burst else None
            cs = num["counts"].iloc[-1].reindex(concepts.get(g, []), fill_value=0)
            row = {
                "g": g,
                "n": int(N[g].iloc[-1]),
                "r": rs[g],
                "b": b,
                "c": [
                    clabel[c]
                    for c in cs[cs > 0]
                    .sort_values(ascending=False)
                    .index[:TOP_CONCEPTS]
                ],
            }
            if row["n"] and not (g in Z and Z[g].iloc[-1] > 0):
                row["r"], row["u"] = [None] * len(PERIODS), 1
            if run.get(g, 0) >= MIN_MONTHS:
                row["p"] = int(run[g])
            if len(members) > 1:
                row["in"] = sorted(c for c in members if g in bursting[c])
            faded = b and b[0] == "fade" and "p" not in row
            (fading if faded else rows).append(row)
        for lst in (rows, fading):
            covered = set().union(*[ancestors(r["g"]) for r in lst])
            lst[:] = [r for r in lst if r["g"] not in covered]
        unit = {"rows": rows, "fading": fading}
        unit["beat"] = beat(num, F, M, set(label))
        shown = [r["g"] for r in rows + fading] + list(unit["beat"]["g"])
        cards = [t for t in tops if {t, *kids.get(t, [])} & set(shown)]
        unit["cards"] = {t: {} for t in cards}
        drawn = [g for t in cards for g in [t, *kids.get(t, [])]]
        keys = list(dict.fromkeys(shown + drawn))
        unit["s"] = series(F, Z, num["nd"], num["src"], keys)
        for g, row in chart(Z, M, num["counts"], num["nm"], keys, axes).items():
            unit["s"][g].update(row)
        if themes:  # theme lines and their member concepts (themes.py)
            Fc = (
                pd.concat([cflags[c] for c in members], axis=1)
                .T.groupby(level=0)
                .any()
                .T
            )
            Zt, Wt, Dt, Ft = theme_frames(
                Z,
                num["counts"],
                num["d_counts"],
                Fc,
                num["d_articles"].isna(),
                themes,
            )
            Mt = theme_index(M, themes)
            ndt = theme_nd(num["nd"], themes)
            numt = {**num, "counts": Wt, "d_counts": Dt}
            unit["beat"]["g"].update(beat(numt, Ft, Mt, set(Wt.columns))["g"])
            keys = [  # theme lines (member concepts are not drawn)
                k
                for k in Wt.columns
                if k.startswith("t:") and (ndt.get(k, 0) or k in unit["beat"]["g"])
            ]
            ts = theme_sources(num["src"], themes)
            unit["s"].update(series(Ft, Zt, ndt, ts, keys))
            NMt = pd.DataFrame(
                {
                    f"t:{k}": num["nm"]
                    .reindex(columns=t["members"], fill_value=0)
                    .sum(axis=1)
                    for k, t in enumerate(themes)
                }
            )
            for g, row in chart(Zt, Mt, Wt, NMt, keys, axes).items():
                unit["s"][g].update(row)
        if len(members) > 1:
            for g in (k for k in unit["s"] if not k.startswith("c:")):
                unit["s"][g]["w"] = where(g, members, CQ, CN)
        # Stories: the page ranks every group and theme together and folds
        # those sharing a driving concept, so each needs its drivers.
        tree_of = {f"t:{k}": t["members"] for k, t in enumerate(themes)}
        unit["co"] = same_articles(
            [h for c in members for h in hits.get(c, [])],
            {g: set(tree_of.get(g, [g])) for g in unit["s"] if not g.startswith("c:")},
        )
        unit["dc"] = {}
        for g in (k for k in unit["s"] if not k.startswith("c:")):
            cs = tree_of.get(g) or [
                c for x in [g, *kids.get(g, [])] for c in concepts.get(x, [])
            ]
            if dc := drivers(num["counts"], cs):
                unit["dc"][g] = dc
        # The driving concepts' own index ("c:<id>"), drawn in the card's
        # chart: their articles and sources in the last DAYS days and series.
        cs = sorted({c for dc in unit["dc"].values() for c, *_ in dc})
        for c in cs:
            unit["s"][f"c:{c}"] = {
                "nd": int(num["nd"].get(c, 0)),
                "ns": len(num["src"].get(c, ())),
            }
        rename = lambda Z: Z.rename(columns=lambda c: f"c:{c}")  # noqa: E731
        for c, row in chart(
            *map(rename, (Z, M, num["counts"], num["nm"])),
            [f"c:{c}" for c in cs],
            axes,
        ).items():
            unit["s"][c].update(row)
        A = num["articles"]
        unit["kpi"] = {
            "articles": int(A.iloc[-1]),
            "total": None
            if db is None
            else int(db[db.country.isin(members)].article_count.sum()),
            "usual": usual_articles(A),
            "subtopics": int(F.iloc[-1].sum()),
            "countries": sum(1 for c in members if bursting[c]),
            "new": sum(
                int((flags[c].iloc[-1] & ~flags[c].iloc[-2]).sum()) for c in members
            ),
        }
        if rows or fading or unit["beat"]["g"]:
            out_units[u] = unit

    out = {
        "region": args.region,
        "generated": f"{date.today():%Y-%m-%d}",
        "week": f"{last:%Y-%m-%d}",
        "periods": list(PERIODS),
        "asof": f"{asof:%Y-%m-%dT%H:%MZ}",
        "beat_start": f"{days[0]:%Y-%m-%d}",
        "days": DAYS,
        "w0": f"{axes[0][0]:%Y-%m-%d}",  # the chart's first week (t0: "week")
        "m0": f"{axes[1][0]:%Y-%m}",  # the chart's first month
        "db_latest": None if db is None else str(db.latest_date.max()),
        "subregions": {s: sorted(cs) for s, cs in sorted(subs.items())},
        "labels": {g: label.get(g, g) for u in out_units.values() for g in u["s"]},
        "themes": [
            {"name": t["name"], "members": t["members"], "headings": t["headings"]}
            for t in themes
        ],
        "clabels": {
            c: clabel[c]
            for u in out_units.values()
            for dc in u["dc"].values()
            for c, *_ in dc
        },
        "cgroup": {  # a driving concept's own group (its heading via labels)
            c: next(g for g, cs in concepts.items() if c in cs)
            for u in out_units.values()
            for dc in u["dc"].values()
            for c, *_ in dc
        },
        "gconcepts": {  # a group's own concepts (the page adds its subgroups')
            g: concepts[g]
            for g in sorted({g for u in out_units.values() for g in u["s"]})
            if g in concepts
        },
        "kids": {
            t: kids[t]
            for t in sorted({t for u in out_units.values() for t in u["cards"]})
            if t in kids
        },
        "heads": {
            h: {"label": schema["headings"][h]["label"], "tops": ts}
            for h in schema["headings"]
            if (
                ts := [
                    t
                    for t in tops
                    if head[t] == h and any(t in u["cards"] for u in out_units.values())
                ]
            )
        },
        "units": out_units,
        "method": {
            "burst": "weekly count >= 2.5x expected from the previous 26 weeks' share, >= 5 articles, Poisson p < 1e-4 (per country)",
            "persistent": f"monthly Baker index above {ELEVATED}x its 2024 mean for the last >= {MIN_MONTHS} complete months, >= {BURST_MIN} articles this week",
            "index": "Baker index per frequency (weekly, monthly): per panel source, share of articles / its std over the 2024 periods, mean weighted by the sources' articles in the period (renormalized over the sources present), 100 = the 2024 mean; q = the weekly index's mean over the last 4 weeks / 100",
            "rank": f"(n - n/q) / sqrt(n/q), n = articles in the last {DAYS} days: the index above usual in counting noise",
            "trend": "rising: the last week's weekly index above its 4-week mean and above each of the 3 weeks before; cooling: below both",
            "ratio": "weekly Baker index (per-source share / its 2024 std, mean weighted by articles over sources publishing in >= 50% of 2024 weeks; regions average their countries) this week / its mean over the comparison period",
        },
    }
    path = OUT / args.region / "overview.json"
    path.write_text(json.dumps(out, separators=(",", ":")))
    k = out_units["region"]["kpi"]
    print(f"region: {len(out_units['region']['rows'])} rows, kpi {k}")
    rows = [r for v in out_units.values() for r in v["rows"]]
    print(
        f"rows {len(rows)}: persistent {sum('p' in r for r in rows)}"
        f" (not bursting {sum('p' in r and not r['b'] for r in rows)}),"
        f" no ratio {sum('u' in r for r in rows)}"
    )
    print(f"{len(out_units)} units; wrote {path} ({path.stat().st_size / 1e3:.0f} KB)")


if __name__ == "__main__":
    main()
