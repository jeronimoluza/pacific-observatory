"""Does ANY weight function beat the plain median?

p2_weight showed w = score loses. The suspected cause is that any non-uniform
weight over CORRECT rows adds variance to the estimator, and that variance
costs more than down-weighting the bad rows saves. If that diagnosis is right,
every scheme that varies weights among good rows loses, and the ranking will
track how much weight variance each one introduces -- so the diagnosis is
falsifiable here rather than assumed.
"""
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from pathlib import Path

rng = np.random.default_rng(20260909)
B = Path("data/prices/enrich/_models/hierlex/hierlex_select_v1_20260908")
OBS = "data/prices/build/global_prices_observations.parquet"
T98 = 0.9376

m = pd.read_parquet("/tmp/p0_joined.parquet")
sub = m[m.below].copy()
f = pq.ParquetFile(OBS)
cols = ["country", "coicop_code", "standard_unit", "unit_value_local",
        "unit_value_usd", "qa_status", "observation_date"]
obs = pd.concat([f.read_row_group(i, columns=cols).to_pandas()
                 for i in range(f.metadata.num_row_groups)], ignore_index=True)
loc = obs[obs.unit_value_local.notna() & (obs.unit_value_local > 0)]
cl = (loc.groupby(["coicop_code", "country", "standard_unit"], observed=True)
        .unit_value_local.agg(cmed="median", cn="size").reset_index())
cl = cl[cl.cn >= 3]
for c in ("coicop_code", "country", "standard_unit"):
    cl[c] = cl[c].astype(str)
for c in ("assigned", "country", "unit"):
    sub[c] = sub[c].astype(str)
j = sub.merge(cl.rename(columns={"coicop_code": "assigned", "standard_unit": "unit"}),
              on=["assigned", "country", "unit"], how="left")
j["lr"] = np.log(j.uv / j.cmed)
OFF = j.loc[j.wrong & j.lr.notna() & np.isfinite(j.lr), "lr"].to_numpy()

oof = pd.read_parquet(B / "audit/implementation_oof_decisions.parquet",
                      columns=["calibrated_correctness_score_oof", "action_correct"])
S, A = oof.calibrated_correctness_score_oof.to_numpy(), oof.action_correct.to_numpy()

pub = obs[(obs.qa_status == "trusted") & obs.unit_value_usd.notna()
          & (obs.unit_value_usd > 0)]
cut = pd.Timestamp.now().normalize() - pd.Timedelta(days=60)
pub = pub[pub.observation_date >= cut]
pub = pub.assign(cell=pub.coicop_code.astype(str) + "|" + pub.country.astype(str)
                 + "|" + pub.standard_unit.astype(str))
vals = [v.to_numpy() for _, v in pub.groupby("cell", observed=True).unit_value_usd]
vals = [v for v in vals if len(v) >= 3]


def wmedian(x, w):
    o = np.argsort(x)
    x, w = x[o], w[o]
    c = np.cumsum(w)
    return x[np.searchsorted(c, c[-1] / 2.0)]


SCHEMES = [
    ("plain median",      lambda s: np.ones_like(s)),
    ("w = score",         lambda s: s),
    ("w = score^4",       lambda s: s ** 4),
    ("w = score^16",      lambda s: s ** 16),
    ("binary 1 / 0.3",    lambda s: np.where(s >= T98, 1.0, 0.3)),
    ("binary 1 / 0.05",   lambda s: np.where(s >= T98, 1.0, 0.05)),
]
T, P = 0.5893, 0.050          # the 95% target
sel = S >= T
sc_ok, sc_bad = S[sel & A], S[sel & ~A]
print("95%% target: correct-row scores n=%s, wrong-row scores n=%s"
      % (format(len(sc_ok), ","), format(len(sc_bad), ",")))
print("  mean score  correct %.3f   wrong %.3f" % (sc_ok.mean(), sc_bad.mean()))

# One draw of contamination, shared by every scheme, so they are compared on
# identical cells rather than on independent noise.
draws = []
for v in vals:
    nb = int(rng.binomial(len(v), P / (1 - P)))
    wg = rng.choice(sc_ok, size=len(v), replace=True)
    if nb:
        bad = rng.choice(v, size=nb, replace=True) * np.exp(
            rng.choice(OFF, size=nb, replace=True))
        wb = rng.choice(sc_bad, size=nb, replace=True)
        m0 = wmedian(v, np.ones(len(v)))
        draws.append((m0, np.concatenate([v, bad]),
                      np.concatenate([wg, wb])))
    else:
        draws.append((wmedian(v, np.ones(len(v))), v, wg))

hdr = "%-18s %10s %9s %9s" % ("scheme", ">5% move", "p99", "wt var")
print("\n" + hdr)
print("-" * len(hdr))
for lab, fn in SCHEMES:
    mv = np.empty(len(draws))
    wv = []
    for i, (m0, x, s) in enumerate(draws):
        w = fn(s)
        mv[i] = abs(wmedian(x, w) - m0) / m0
        wv.append(w.std() / max(w.mean(), 1e-9))
    print("%-18s %9.1f%% %8.1f%% %9.3f" % (
        lab, (mv > .05).mean() * 100, np.quantile(mv, .99) * 100, np.mean(wv)))
print("\n'wt var' = mean coefficient of variation of the weights within a cell.")
