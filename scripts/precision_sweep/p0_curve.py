"""Phase 0, part 1: the honest coverage-vs-precision curve, on nested OOF.

Control first: reproduce the two operating points the bundle ships, from the
same rows it computed them on. If those do not come back to the published
figures, nothing downstream is trustworthy.
"""

import numpy as np
import pandas as pd
from pathlib import Path

B = Path.home() / "po/data/prices/enrich/_models/hierlex/hierlex_select_v1_20260908"
oof = pd.read_parquet(B / "audit/implementation_oof_decisions.parquet")

print(f"OOF rows: {len(oof):,}   folds: {sorted(oof.outer_fold.unique())}")

s = oof["calibrated_correctness_score_oof"].to_numpy(float)
c = oof["action_correct"].to_numpy(bool)
n = len(s)

TAU_PROD = 0.9436536386510268
TAU_E98 = 0.9376235851910657


def at_tau(tau):
    a = s >= tau
    return dict(tau=tau, accepted=int(a.sum()),
                precision=float(c[a].mean()) if a.any() else float("nan"),
                coverage=float((c & a).sum() / n))


print("\n=== CONTROL: reproduce the shipped operating points ===")
print(f"{'policy':<20}{'tau':>12}{'accepted':>10}{'precision':>11}{'coverage':>10}")
for nm, t, pp, pc in (("conservative_risk", TAU_PROD, 0.9816442, 0.7744623),
                      ("empirical_98", TAU_E98, 0.9800024, 0.7835973)):
    r = at_tau(t)
    ok = abs(r["precision"] - pp) < 1e-6 and abs(r["coverage"] - pc) < 1e-6
    print(f"{nm:<20}{t:>12.7f}{r['accepted']:>10,}{r['precision']:>10.4%}"
          f"{r['coverage']:>10.4%}   {'MATCH' if ok else 'MISMATCH'}")
    if not ok:
        print(f"    published: precision {pp:.4%}  coverage {pc:.4%}")

# --- solve for the tau that hits each PRECISION target -----------------------
order = np.argsort(-s)
cs, cc = s[order], c[order]
cum = np.cumsum(cc.astype(float)) / (np.arange(n) + 1)


def for_target(target):
    ok = np.where(cum >= target)[0]
    if not len(ok):
        return None
    i = ok[-1]
    tau = float(cs[i])
    a = s >= tau
    return dict(target=target, tau=tau, accepted=int(a.sum()),
                precision=float(c[a].mean()), coverage=float((c & a).sum() / n))


base = at_tau(TAU_PROD)
print("\n=== READING A: 95/92/90 are PRECISION TARGETS ===")
print("(what 'lower the 98% precision requirement' most likely means)")
print(f"{'target':>8}{'tau':>12}{'accepted':>11}{'precision':>11}{'coverage':>10}"
      f"{'  vs prod cov':>14}{'rows gained':>13}")
for t in (0.98, 0.97, 0.96, 0.95, 0.92, 0.90, 0.85, 0.80):
    r = for_target(t)
    if r is None:
        print(f"{t:>8.0%}   unreachable")
        continue
    print(f"{t:>8.0%}{r['tau']:>12.6f}{r['accepted']:>11,}{r['precision']:>10.3%}"
          f"{r['coverage']:>10.3%}{r['coverage']-base['coverage']:>+13.3%}"
          f"{r['accepted']-base['accepted']:>+13,}")

print("\n=== READING B: 95/92/90 are TAU VALUES ===")
print(f"{'tau':>8}{'accepted':>11}{'precision':>11}{'coverage':>10}"
      f"{'  vs prod cov':>14}{'rows gained':>13}")
for t in (TAU_PROD, 0.95, 0.92, 0.90, 0.85, 0.80, 0.75):
    r = at_tau(t)
    tag = " (prod)" if t == TAU_PROD else ""
    print(f"{t:>8.4f}{r['accepted']:>11,}{r['precision']:>10.3%}{r['coverage']:>10.3%}"
          f"{r['coverage']-base['coverage']:>+13.3%}{r['accepted']-base['accepted']:>+13,}{tag}")

# --- food & beverage only ----------------------------------------------------
fb = oof["gold"].astype(str).str.startswith(("01.", "02."))
print(f"\n=== FOOD & BEVERAGE ONLY ({fb.sum():,} of {n:,} OOF rows) ===")
sf, cf = s[fb.to_numpy()], c[fb.to_numpy()]
nf = len(sf)
bf = sf >= TAU_PROD
print(f"production point: precision {cf[bf].mean():.3%}  coverage {(cf&bf).sum()/nf:.3%}")
print(f"{'target':>8}{'tau':>12}{'precision':>11}{'coverage':>10}{'  vs prod':>11}")
of = np.argsort(-sf)
cumf = np.cumsum(cf[of].astype(float)) / (np.arange(nf) + 1)
for t in (0.98, 0.95, 0.92, 0.90):
    ok = np.where(cumf >= t)[0]
    if not len(ok):
        print(f"{t:>8.0%}   unreachable")
        continue
    tau = float(sf[of][ok[-1]])
    a = sf >= tau
    print(f"{t:>8.0%}{tau:>12.6f}{cf[a].mean():>10.3%}{(cf&a).sum()/nf:>10.3%}"
          f"{(cf&a).sum()/nf - (cf&bf).sum()/nf:>+11.3%}")
