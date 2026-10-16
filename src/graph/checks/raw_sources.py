"""Raw checks per source on ``prices.raw`` (PX-50).

- red: a silent zero, the week's last ledger record says ``ok_norows``, the week has 0 rows
  on disk and the source's baseline is > 0. A fetcher (it only writes observations newer
  than its cutoff) is red only if it brought rows in every collect week of the baseline
  (at least 3) or its last ``observation_date`` is older than 3 median gaps between its
  observation dates (at least 7 days) at the week's Monday; otherwise yellow;
- red: rows dated after today UTC (#8), from ``observation_date`` of the fetcher CSV;
- yellow: ledger status timeout, stalled, fail, blocked or runner_error;
- yellow: an active manifest that is in no ledger of the week.

The week's ledgers are ``<logs>/<wk>/ledger_path`` plus the retry runs next to them
(``_fullrun_<YYYYMMDD>_<HHMMSS>/status.jsonl`` dated in the week), in run order; a later
record replaces an earlier one. The baseline is the median weekly row count over the
collect weeks among the ``n`` ISO weeks before the target one (a week where no source has
rows had no collect), counted from the source's first week on disk (an absent week counts
0): spiders by lines of
``raw_items/<source>_<YYYYMMDD>_<HHMMSS>.jsonl`` (largest file of the week), fetchers by
rows of ``price_observations.csv`` grouped by the ISO week of ``scrape_ts``.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

NODE = "prices.raw"
DATA_ROOT = Path.home() / "po/data/prices"
LOGS_ROOT = Path.home() / "po/logs/weekly"
YELLOW_STATUSES = {"timeout", "stalled", "fail", "blocked", "runner_error"}
_RUN_TS = re.compile(r"_(\d{8})_\d{6}\.jsonl$")


def _week_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def ledger_records(ledgers: list[Path]) -> dict[tuple[str, str], dict]:
    out = {}
    for ledger in ledgers:
        if not ledger.exists():
            continue
        for line in ledger.read_text().splitlines():
            if line.strip():
                e = json.loads(line)
                out[(e["country"], e["source"])] = e
    return out


def _lines(path: Path) -> int:
    n = 0
    with open(path, "rb") as fh:
        while chunk := fh.read(1 << 20):
            n += chunk.count(b"\n")
    return n


def spider_weeks(source_dir: Path, start: date, end: date) -> tuple[dict[date, int], date | None]:
    """Largest run file per ISO week in [start, end), and the first week with any file."""
    weeks: dict[date, int] = {}
    first = None
    for f in (source_dir / "raw_items").glob("*.jsonl"):
        m = _RUN_TS.search(f.name)
        if not m:
            continue
        wk = _week_of(datetime.strptime(m[1], "%Y%m%d").date())
        first = wk if first is None or wk < first else first
        if start <= wk < end:
            weeks[wk] = max(weeks.get(wk, 0), _lines(f))
    return weeks, first


def week_ledgers(listed: list[Path], start: date) -> list[Path]:
    """The listed ledgers plus the sibling ``_fullrun_*`` runs dated in the ISO week, in run order."""
    days = {(start + timedelta(days=i)).strftime("%Y%m%d") for i in range(7)}
    found = set(listed)
    for parent in {p.parent.parent for p in listed}:
        found |= {p for p in parent.glob("_fullrun_*/status.jsonl") if p.parent.name[9:17] in days}
    return sorted(found, key=lambda p: p.parent.name)


def obs_dates(csv_path: Path) -> tuple[date | None, float | None]:
    """Last observation_date of a fetcher CSV and the median gap in days between its dates."""
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.csv as pcsv

    t = pcsv.read_csv(csv_path, convert_options=pcsv.ConvertOptions(
        include_columns=["observation_date"], column_types={"observation_date": pa.string()}))
    ds = []
    for v in pc.unique(pc.utf8_slice_codeunits(t["observation_date"], 0, 10)).to_pylist():
        try:
            ds.append(date.fromisoformat(v))
        except (TypeError, ValueError):
            pass
    ds.sort()
    gaps = [(b - a).days for a, b in zip(ds, ds[1:])]
    return (ds[-1] if ds else None), (statistics.median(gaps) if gaps else None)


def fetcher_weeks(csv_path: Path, today: date) -> tuple[dict[date, int], date | None, int]:
    """Rows per ISO week of scrape_ts, first such week, and rows dated after today."""
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.csv as pcsv

    header = csv_path.open(encoding="utf-8").readline().strip().split(",")
    cols = [c for c in ("observation_date", "scrape_ts") if c in header]
    t = pcsv.read_csv(csv_path, convert_options=pcsv.ConvertOptions(
        include_columns=cols, column_types={c: pa.string() for c in cols}))
    future = 0
    if "observation_date" in cols:
        d = pc.utf8_slice_codeunits(t["observation_date"], 0, 10)
        future = pc.sum(pc.fill_null(pc.greater(d, today.isoformat()), False).cast(pa.int64())).as_py() or 0
    weeks: dict[date, int] = {}
    if "scrape_ts" in cols:
        days = pc.value_counts(pc.utf8_slice_codeunits(t["scrape_ts"], 0, 10)).to_pylist()
        for v in days:
            try:
                wk = _week_of(date.fromisoformat(v["values"]))
            except (TypeError, ValueError):
                continue
            weeks[wk] = weeks.get(wk, 0) + v["counts"]
    return weeks, min(weeks, default=None), future


def source_dir(data_root: Path, region: str | None, country: str, source: str) -> Path | None:
    hits = sorted(data_root.glob(f"{region or '*'}/*/{country}/{source}"))
    return hits[0] if hits else None


def read(week: str, ledgers: list[Path] | None = None, data_root: Path = DATA_ROOT,
         logs_root: Path = LOGS_ROOT, countries: list[str] | None = None, n: int = 4,
         today: date | None = None) -> list[dict]:
    today = today or datetime.now(timezone.utc).date()
    y, w = week.split("-W")
    start = date.fromisocalendar(int(y), int(w), 1)
    if ledgers is None:
        listed = (logs_root / week / "ledger_path").read_text().strip()
        ledgers = week_ledgers([Path(p) for p in listed.split(",") if p], start)
    records = ledger_records(ledgers)
    from prices.config import discover_prices_configs
    import yaml

    active = {}
    for p in discover_prices_configs():
        if (yaml.safe_load(p.read_text()) or {}).get("active", True):
            active[(p.parent.name, p.stem)] = p.parent.parent.parent.name
    keys = set(records) | set(active)
    rows = []
    for country, source in sorted(keys):
        if countries and country not in countries:
            continue
        e = records.get((country, source), {})
        sdir = source_dir(data_root, e.get("region") or active.get((country, source)), country, source)
        weeks, first, future = {}, None, 0
        if sdir:
            weeks, first = spider_weeks(sdir, start - timedelta(weeks=n), start + timedelta(weeks=1))
            if (sdir / "price_observations.csv").exists():
                fw, f2, future = fetcher_weeks(sdir / "price_observations.csv", today)
                weeks = {k: max(weeks.get(k, 0), fw.get(k, 0)) for k in set(weeks) | set(fw)}
                first = min([x for x in (first, f2) if x], default=None)
        last_obs, obs_gap = None, None
        if (e.get("scaffolding") == "fetcher" and e.get("status") == "ok_norows" and not weeks.get(start)
                and sdir and (sdir / "price_observations.csv").exists()):
            last_obs, obs_gap = obs_dates(sdir / "price_observations.csv")
        rows.append({
            "country": country, "source": source, "status": e.get("status"),
            "new_rows": e.get("new_rows"), "in_ledger": bool(e), "active": (country, source) in active,
            "dir": str(sdir) if sdir else None, "week_rows": weeks.get(start, 0),
            "future_rows": future, "scaffolding": e.get("scaffolding"),
            "last_obs": last_obs, "obs_gap": obs_gap, "_weeks": weeks, "_first": first,
        })
    prior = [start - timedelta(weeks=i) for i in range(n, 0, -1)]
    collected = {wk for r in rows for wk, v in r["_weeks"].items() if v}
    prior = [wk for wk in prior if wk in collected]
    for r in rows:
        weeks, first = r.pop("_weeks"), r.pop("_first")
        mine = [weeks.get(wk, 0) for wk in prior if first and wk >= first]
        r["baseline"] = statistics.median(mine) if mine else None
        r["steady"] = len(mine) >= 3 and all(mine)
        r["overdue"] = bool(r["last_obs"] and r["obs_gap"]
                            and (start - r["last_obs"]).days > max(7, 3 * r["obs_gap"]))
    return rows


def check(rows: list[dict]) -> list[dict]:
    """Registry hook over the collect observer rows: ledger statuses only. The baseline
    and the dates need the raw files, so the node also points at the direct run."""
    raw = [r for r in rows if r["node"] == NODE and r["partition"] != "_week"]
    if not raw:
        return []
    out = [{"node": NODE, "partition": r["partition"], "color": "amarillo",
            "msg": f"status {r['extra'].get('status')}"}
           for r in raw if r["extra"].get("status") in YELLOW_STATUSES]
    out.append({"node": NODE, "partition": "*", "color": "amarillo",
                "msg": "ceros vs baseline y fechas futuras requieren corrida directa: "
                       "python -m graph.checks.raw_sources --week <wk>"})
    return out


def evaluate(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        part = f"{r['country']}/{r['source']}"
        if r["status"] == "ok_norows" and r["baseline"] and not r["week_rows"]:
            if r["scaffolding"] != "fetcher" or r["steady"] or r["overdue"]:
                out.append({"node": NODE, "partition": part, "color": "rojo",
                            "msg": f"cero silencioso: ok_norows con baseline {r['baseline']:g}"
                                   + (f", ultima observation_date {r['last_obs']}" if r["last_obs"] else "")})
            else:
                out.append({"node": NODE, "partition": part, "color": "amarillo",
                            "msg": f"fetcher sin delta: ok_norows con baseline {r['baseline']:g}, "
                                   f"ultima observation_date {r['last_obs']} (gap mediano {r['obs_gap']})"})
        if r["future_rows"]:
            out.append({"node": NODE, "partition": part, "color": "rojo",
                        "msg": f"#8 {r['future_rows']:,} filas con observation_date > hoy UTC"})
        if r["status"] in YELLOW_STATUSES:
            out.append({"node": NODE, "partition": part, "color": "amarillo", "msg": f"status {r['status']}"})
        if r["active"] and not r["in_ledger"]:
            out.append({"node": NODE, "partition": part, "color": "amarillo",
                        "msg": "manifiesto activo sin registro en los ledgers de la semana"})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m graph.checks.raw_sources")
    ap.add_argument("--week", required=True, help="ISO week, e.g. 2026-W42")
    ap.add_argument("--ledger", type=Path, action="append",
                    help="status.jsonl in run order (default: <logs>/<wk>/ledger_path)")
    ap.add_argument("--data-root", type=Path, default=DATA_ROOT)
    ap.add_argument("--logs-root", type=Path, default=LOGS_ROOT)
    ap.add_argument("--countries", help="comma-separated slugs or a panel name (panel36)")
    ap.add_argument("-n", type=int, default=4, help="weeks in the baseline")
    ap.add_argument("--today", type=date.fromisoformat, help="YYYY-MM-DD (default: today UTC)")
    a = ap.parse_args(argv)
    countries = None
    if a.countries:
        from prices.weekly.panels import resolve_countries
        countries = resolve_countries(a.countries)
    rows = read(a.week, a.ledger, a.data_root, a.logs_root, countries, a.n, a.today)
    findings = evaluate(rows)
    for f in findings:
        print(f"{f['color']:<8} {f['node']}  {f['partition']:<48} {f['msg']}")
    by = {c: sum(f["color"] == c for f in findings) for c in ("rojo", "amarillo")}
    silent = sum(f["msg"].startswith("cero silencioso") for f in findings)
    print(f"{len(rows)} fuentes; rojo {by['rojo']} (ceros silenciosos {silent}); amarillo {by['amarillo']}")
    return 1 if by["rojo"] else 0


if __name__ == "__main__":
    sys.exit(main())
