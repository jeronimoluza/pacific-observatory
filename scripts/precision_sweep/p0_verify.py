"""Is the null result real, or is my instrument broken?

Three checks:
  1. AUC of |robust z| as a discriminator of misclassification (expect ~0.50)
  2. CONTROL: the same statistic against rows that fail the absolute USD
     plausibility band -- a defect it SHOULD catch. If that AUC is high, the
     column works and the null above is a property of the world, not a bug.
  3. Does density help? Stratify by cell support.
"""
import pandas as pd, numpy as np

m = pd.read_parquet("/tmp/p0_joined.parquet")
TAU = 0.9436536386510268


def auc(score, pos):
    ok = np.isfinite(score) & np.isfinite(pos.astype(float))
    s, y = np.asarray(score)[ok], np.asarray(pos)[ok].astype(bool)
    if y.all() or not y.any():
        return float("nan"), int(ok.sum())
    r = pd.Series(s).rank().to_numpy()
    n1, n0 = y.sum(), (~y).sum()
    return float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)), int(ok.sum())


sub = m[m.below].copy()
sub["absz"] = sub.absz.abs()

a, n = auc(sub.absz, sub.wrong)
se = np.sqrt(a * (1 - a) / min((sub.wrong).sum(), (~sub.wrong).sum())) if np.isfinite(a) else np.nan
print("=== 1. |robust z| as a detector of MISCLASSIFICATION ===")
print(f"   AUC = {a:.4f}  (n={n:,}, ~±{1.96*se:.3f})   0.50 = coin flip")

# two-proportion test at the shipped k
w, r = sub[sub.wrong], sub[~sub.wrong]
p1, n1 = w.outlier.fillna(False).mean(), len(w)
p0, n0 = r.outlier.fillna(False).mean(), len(r)
pp = (p1 * n1 + p0 * n0) / (n1 + n0)
z = (p1 - p0) / np.sqrt(pp * (1 - pp) * (1 / n1 + 1 / n0))
print(f"   flag rate wrong {p1:.1%} vs correct {p0:.1%};  z = {z:.2f}"
      f"  ({'n.s.' if abs(z) < 1.96 else 'significant'})")

print("\n=== 2. CONTROL: same statistic vs an implausible ABSOLUTE unit value ===")
# The USD plausibility band from qa.py; a row outside it is genuinely anomalous.
BANDS = {"kg": (0.20, 200.0), "lt": (0.05, 200.0),
         "item": (0.005, 500.0), "unit": (0.005, 500.0)}
lo = sub.unit.map(lambda u: BANDS.get(u, (np.nan, np.nan))[0])
hi = sub.unit.map(lambda u: BANDS.get(u, (np.nan, np.nan))[1])
implaus = (sub.uv_usd < lo) | (sub.uv_usd > hi)
a2, n2 = auc(sub.absz, implaus)
print(f"   AUC = {a2:.4f}  (n={n2:,}, {int(implaus.sum()):,} implausible rows)")
print("   -> if this is well above 0.50 the column is healthy and check 1 stands")

print("\n=== 3. Does a denser cell rescue it? ===")
print(f"{'cell_n':>12}{'rows':>9}{'wrong':>8}{'AUC':>9}{'flag@k5 wrong':>16}{'correct':>10}")
for lab, q in (("<10", sub.cell_n < 10), ("10-99", sub.cell_n.between(10, 99)),
               ("100-999", sub.cell_n.between(100, 999)), ("1000+", sub.cell_n >= 1000)):
    d = sub[q]
    if len(d) < 50:
        print(f"{lab:>12}{len(d):>9,}   (too few)")
        continue
    aa, _ = auc(d.absz, d.wrong)
    dw, dr = d[d.wrong], d[~d.wrong]
    print(f"{lab:>12}{len(d):>9,}{len(dw):>8,}{aa:>9.3f}"
          f"{dw.outlier.fillna(False).mean():>15.1%}{dr.outlier.fillna(False).mean():>10.1%}")

print("\n=== 4. Food & beverage only ===")
fb = sub[sub.code.astype(str).str.startswith(("01.", "02."))]
afb, nfb = auc(fb.absz, fb.wrong)
print(f"   n={len(fb):,} ({fb.wrong.sum():,} wrong)   AUC = {afb:.4f}")

print("\n=== 5. how far apart are the two price distributions, really? ===")
lw = np.log(sub.loc[sub.wrong, "uv_usd"].replace(0, np.nan).dropna())
lr = np.log(sub.loc[~sub.wrong, "uv_usd"].replace(0, np.nan).dropna())
pooled = np.sqrt((lw.var() + lr.var()) / 2)
print(f"   mean log(uv) wrong {lw.mean():.3f} vs correct {lr.mean():.3f}")
print(f"   Cohen's d = {(lw.mean()-lr.mean())/pooled:.3f}   (0.2 = 'small')")
