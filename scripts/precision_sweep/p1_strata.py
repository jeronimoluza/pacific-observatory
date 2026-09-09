"""Ideas 2 and 3: does per-stratum calibration buy anything?

  Idea 2: is the dispersion gate dead EVERYWHERE, or only on average?
          Per-category AUC. If some categories separate, a per-category k helps.
  Idea 3: per-stratum tau instead of one global tau, generalising empirical_98.
          Cross-validated on the OOF fold column so the tau is never scored on
          the rows that chose it.
"""
import pandas as pd, numpy as np
from pathlib import Path

B = Path("data/prices/enrich/_models/hierlex/hierlex_select_v1_20260908")


def auc(score, pos):
    ok = np.isfinite(score)
    s, y = np.asarray(score)[ok], np.asarray(pos)[ok].astype(bool)
    if y.all() or not y.any() or len(y) < 30:
        return np.nan
    r = pd.Series(s).rank().to_numpy()
    n1, n0 = y.sum(), (~y).sum()
    return float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


# ---------------------------------------------------------------- IDEA 2 ----
m = pd.read_parquet("/tmp/p0_joined.parquet")
sub = m[m.below].copy()
sub["absz"] = sub.absz.abs()
sub["div"] = sub.code.astype(str).str[:4]

print("=== IDEA 2: is the price filter dead everywhere, or only on average? ===")
print("AUC of |robust z| vs misclassification, per COICOP class\n")
print(f"{'class':<8}{'rows':>7}{'wrong':>7}{'AUC':>8}   verdict")
rows = []
for c, d in sub.groupby("div"):
    if len(d) < 150 or d.wrong.sum() < 25:
        continue
    a = auc(d.absz, d.wrong)
    if np.isnan(a):
        continue
    rows.append((c, len(d), int(d.wrong.sum()), a))
rows.sort(key=lambda r: -r[3])
for c, n, w, a in rows:
    v = "SEPARATES" if a > 0.60 else ("inverted" if a < 0.40 else "coin flip")
    print(f"{c:<8}{n:>7,}{w:>7,}{a:>8.3f}   {v}")
best = [r for r in rows if r[3] > 0.60]
print(f"\n{len(best)} of {len(rows)} classes beat AUC 0.60"
      f"  ({sum(r[1] for r in best):,} of {sum(r[1] for r in rows):,} rows)")

# Same question by country.
print("\nby country (>=200 rows):")
sc = []
for c, d in sub.groupby(sub.country.astype(str)):
    if len(d) < 200 or d.wrong.sum() < 30:
        continue
    a = auc(d.absz, d.wrong)
    if not np.isnan(a):
        sc.append((c, len(d), a))
sc.sort(key=lambda r: -r[2])
for c, n, a in sc[:6] + [("...", 0, np.nan)] + sc[-3:]:
    if n == 0:
        print("   ...")
        continue
    print(f"   {c:<24}{n:>7,}{a:>8.3f}")

# ---------------------------------------------------------------- IDEA 3 ----
print("\n\n=== IDEA 3: per-stratum tau, cross-validated ===")
oof = pd.read_parquet(B / "audit/implementation_oof_decisions.parquet",
                      columns=["gold_row_id", "calibrated_correctness_score_oof",
                               "action_correct", "gold", "country", "outer_fold"])
oof = oof.rename(columns={"calibrated_correctness_score_oof": "s",
                          "action_correct": "c"})
# Leaf support in gold = the risk axis identified earlier.
sup = oof.gold.value_counts()
oof["sup"] = oof.gold.map(sup)
oof["bucket"] = pd.cut(oof["sup"], [0, 100, 500, 2000, 10000, 10**9],
                       labels=["<100", "100-499", "500-1999", "2k-10k", "10k+"])


def tau_for(s, c, target):
    o = np.argsort(-s)
    cum = np.cumsum(c[o].astype(float)) / (np.arange(len(o)) + 1)
    ok = np.where(cum >= target)[0]
    return float(s[o][ok[-1]]) if len(ok) else 1.01


TARGET = 0.95
print(f"target precision {TARGET:.0%}, 5-fold CV (tau fitted on 4 folds, scored on the 5th)\n")
for label, keyfn in (("GLOBAL tau (baseline)", None),
                     ("per SUPPORT BUCKET", lambda d: d["bucket"].astype(str)),
                     ("per COUNTRY", lambda d: d["country"].astype(str))):
    acc = np.zeros(len(oof), bool)
    for f in sorted(oof.outer_fold.unique()):
        tr, te = oof[oof.outer_fold != f], oof[oof.outer_fold == f]
        if keyfn is None:
            t = tau_for(tr.s.to_numpy(), tr.c.to_numpy(), TARGET)
            acc[oof.outer_fold.to_numpy() == f] = te.s.to_numpy() >= t
        else:
            ktr, kte = keyfn(tr), keyfn(te)
            gt = {k: tau_for(d.s.to_numpy(), d.c.to_numpy(), TARGET)
                  for k, d in tr.groupby(ktr) if len(d) >= 200}
            glob = tau_for(tr.s.to_numpy(), tr.c.to_numpy(), TARGET)
            thr = kte.map(gt).fillna(glob).to_numpy()
            acc[oof.outer_fold.to_numpy() == f] = te.s.to_numpy() >= thr
    c = oof.c.to_numpy()
    prec = c[acc].mean()
    cov = (c & acc).sum() / len(oof)
    print(f"  {label:<24} precision {prec:.3%}   coverage {cov:.3%}   "
          f"accepted {acc.sum():,}")
