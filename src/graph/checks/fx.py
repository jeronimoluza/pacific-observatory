"""Checks on the ``fx`` node (PX-53): the shared FX cache and what the explorer said about it.

- red: the cache's newest date is more than ``FX_MAX_LAG_DAYS`` before today UTC
  (the rule ``prices.stage_b_fx.require_fresh_fx`` applies before Stage B);
- red: a line without exactly 4 comma-separated fields, or a date/rate that does not parse;
- yellow: an ``FX EXCURSION`` the explorer logged (an upstream rate defect);
- yellow: a country the explorer gave no local-currency overlay.

Excursions and overlays are computed by ``prices.explorer.aggregate`` from the build's
observations, not from the cache, so they are read from that build's log (``--log``).
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

NODE = "fx"
CACHE = Path.home() / "po/data/prices/_fx/fx_cache.csv"

_EXCURSION = re.compile(
    r"FX EXCURSION: (\S+) leaves .* for \d+ month\(s\) \((\S+)\.\.(\S+)\)"
)
_NO_OVERLAY = re.compile(r"get no overlay: (.*)$")
_DECLARED = re.compile(r"(\w+) \(declared ([^)]*)\)")


def read_cache(path: Path) -> dict:
    n, n_bad, bad, last = 0, 0, [], None
    with open(path, encoding="utf-8") as fh:
        next(fh)
        for i, line in enumerate(fh, start=2):
            n += 1
            parts = line.rstrip("\n").split(",")
            try:
                if len(parts) != 4:
                    raise ValueError(f"{len(parts)} campos")
                d = date.fromisoformat(parts[1])
                float(parts[2])
            except ValueError as e:
                n_bad += 1
                if len(bad) < 5:
                    bad.append(f"línea {i}: {e}")
                continue
            if last is None or d > last:
                last = d
    return {
        "kind": "cache",
        "path": str(path),
        "lines": n,
        "last_date": last,
        "bad_lines": n_bad,
        "bad_examples": bad,
    }


def read_logs(paths: list[Path]) -> list[dict]:
    excursions, missing = {}, {}
    for p in paths:
        for line in Path(p).read_text(encoding="utf-8", errors="replace").splitlines():
            if m := _EXCURSION.search(line):
                excursions[(m[1], m[2], m[3])] = line.split("FX EXCURSION: ", 1)[1]
            elif m := _NO_OVERLAY.search(line):
                missing.update(dict(_DECLARED.findall(m[1])))
    return [
        {"kind": "excursion", "country": c, "start": s, "end": e, "line": t}
        for (c, s, e), t in sorted(excursions.items())
    ] + [
        {"kind": "no_overlay", "country": c, "declared": d}
        for c, d in sorted(missing.items())
    ]


def read(
    cache: Path = CACHE,
    logs: list[Path] | None = None,
    today: date | None = None,
    countries: list[str] | None = None,
) -> list[dict]:
    today = today or datetime.now(timezone.utc).date()
    rows = [{**read_cache(cache), "today": today}]
    rows += [
        r
        for r in read_logs(logs or [])
        if countries is None or r["country"] in countries
    ]
    return rows


def check(rows: list[dict]) -> list[dict]:
    """Registry hook: no observer reads the cache, so this only points at the direct run."""
    if not any(r["node"] == NODE for r in rows):
        return []
    return [
        {
            "node": NODE,
            "partition": "*",
            "color": "amarillo",
            "msg": "requiere corrida directa: python -m graph.checks.fx --log <build log>",
        }
    ]


def evaluate(rows: list[dict]) -> list[dict]:
    from prices.stage_b_fx import FX_MAX_LAG_DAYS

    out = []
    for r in rows:
        if r["kind"] == "cache":
            floor = r["today"] - timedelta(days=FX_MAX_LAG_DAYS)
            red = []
            if r["last_date"] is None or r["last_date"] < floor:
                red.append(
                    f"cache termina {r['last_date']}, < hoy - {FX_MAX_LAG_DAYS} d ({floor})"
                )
            if r["bad_lines"]:
                red.append(
                    f"{r['bad_lines']} líneas mal formadas: {'; '.join(r['bad_examples'])}"
                )
            out += [
                {"node": NODE, "partition": "*", "color": "rojo", "msg": m} for m in red
            ]
        elif r["kind"] == "excursion":
            out.append(
                {
                    "node": NODE,
                    "partition": r["country"],
                    "color": "amarillo",
                    "msg": f"excursión {r['start']}..{r['end']}: {r['line']}",
                }
            )
        else:
            out.append(
                {
                    "node": NODE,
                    "partition": r["country"],
                    "color": "amarillo",
                    "msg": f"sin overlay de FX (moneda declarada {r['declared'] or '?'})",
                }
            )
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m graph.checks.fx")
    ap.add_argument("--cache", type=Path, default=CACHE)
    ap.add_argument(
        "--log",
        type=Path,
        action="append",
        default=[],
        help="build log with the explorer's FX warnings (repeatable)",
    )
    ap.add_argument(
        "--today", type=date.fromisoformat, help="YYYY-MM-DD (default: today UTC)"
    )
    ap.add_argument(
        "--countries", help="comma-separated slugs or a panel name (panel36)"
    )
    a = ap.parse_args(argv)
    countries = None
    if a.countries:
        from prices.weekly.panels import resolve_countries

        countries = resolve_countries(a.countries)
    rows = read(a.cache, a.log, a.today, countries)
    print(
        f"cache {rows[0]['path']}: {rows[0]['lines']:,} líneas, última fecha {rows[0]['last_date']}"
    )
    findings = evaluate(rows)
    for f in findings:
        print(f"{f['color']:<8} {f['node']}  {f['partition']:<24} {f['msg']}")
    return 1 if any(f["color"] == "rojo" for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
