"""`fuel.country`: one row per built country from
`outputs/fuel/<region>/<subregion>/<country>/fuel_{product_local,family_usd}_prices.csv`
plus the latest `outputs/fuel/regime_alerts/<date>.csv`. The first declared output
path whose root exists on this machine wins. Drift: no rows, a non-retail
price_basis, families no longer shown (last published day, carry-forward of
fuel.fill_rule included, older than STALE_DAYS), regime alerts."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from graph.observe import mtime, root_of, row

STALE_DAYS = 31  # the fill rule already carries announcement prices while alive


def _first_existing(node, role: str) -> str | None:
    for p in node.paths:
        if p.get("role", "output") == role:
            path = str(Path(p["path"]).expanduser())
            if root_of(path).exists():
                return path
    return None


def _alerts(template: str | None) -> dict[str, dict[str, int]]:
    import pandas as pd

    if not template:
        return {}
    files = sorted(root_of(template).glob("*.csv"))
    if not files:
        return {}
    df = pd.read_csv(files[-1], usecols=["detector", "iso3"])
    out: dict[str, dict[str, int]] = {}
    for (iso3, det), n in df.groupby(["iso3", "detector"]).size().items():
        out.setdefault(iso3, {})[det] = int(n)
    return out


def observe(node) -> list[dict]:
    import pandas as pd

    template = _first_existing(node, "output")
    if template is None:
        return []
    alerts = _alerts(_first_existing(node, "state"))
    today = pd.Timestamp(datetime.now(timezone.utc).date())
    out = []
    for fam_path in sorted(root_of(template).glob("*/*/*/fuel_family_usd_prices.csv")):
        region, country = fam_path.parts[-4], fam_path.parts[-2]
        fam = pd.read_csv(fam_path, low_memory=False)
        prod_path = fam_path.with_name("fuel_product_local_prices.csv")
        prod = (
            pd.read_csv(
                prod_path, usecols=["fuel_family", "observed_on", "is_forward_filled"]
            )
            if prod_path.exists()
            else pd.DataFrame()
        )
        last_obs, shown, basis, drift = {}, {}, {}, []
        if not prod.empty:
            real = prod[~prod["is_forward_filled"].astype(str).eq("True")]
            last_obs = real.groupby("fuel_family")["observed_on"].max().to_dict()
        if not fam.empty:
            shown = fam.groupby("fuel_family")["observation_date"].max().to_dict()
        if not fam.empty and "price_basis" in fam:
            basis = (
                fam.sort_values("observation_date")
                .groupby("fuel_family")["price_basis"]
                .last()
                .fillna("retail")
                .to_dict()
            )
        iso3 = fam["iso3"].iloc[0] if not fam.empty else None
        if fam.empty:
            drift.append("no_rows")
        odd = {f: b for f, b in basis.items() if b != "retail"}
        if odd:
            drift.append(
                "fallback: " + ",".join(f"{f}={b}" for f, b in sorted(odd.items()))
            )
        old = {
            f: d
            for f, d in shown.items()
            if (today - pd.Timestamp(d)).days > STALE_DAYS
        }
        if old:
            drift.append(
                "stale: " + ",".join(f"{f}@{d}" for f, d in sorted(old.items()))
            )
        reg = alerts.get(iso3, {})
        if reg:
            drift.append(
                "regime_alerts: " + ",".join(f"{k}={v}" for k, v in sorted(reg.items()))
            )
        out.append(
            row(
                node,
                f"{region}/{country}",
                not fam.empty,
                len(fam),
                mtime(fam_path),
                drift=drift,
                extra={
                    "iso3": iso3,
                    "last_obs": last_obs,
                    "last_shown": shown,
                    "price_basis": basis,
                    "stale_families": sorted(old),
                    "regime_alerts": reg,
                },
            )
        )
    return out
