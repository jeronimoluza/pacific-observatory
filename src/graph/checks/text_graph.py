"""Checks on the text observer rows (TX-15, TX-17 and the merge and ownership rules of text.yaml).

- ``text.corpus`` (one row per owner/run/region): red when merge refused (pending dir
  without PLAN.tsv), when a run with ``.done`` is not merged after 2 days, or when a region
  ran (events log) and staged 0 rows; yellow when a done run is not merged yet, awaits
  sign-off, or has no ``.done``;
- ``text.delta`` (one row per owner/region/source of the newest run): red for 0 rows in two
  consecutive done runs after a baseline, or a source staged by an owner that does not own
  it; yellow for 0 rows once, or fail;
- ``text.epu``: yellow when epu.csv is older than its country's params.json;
- ``text.dashboard``: yellow when older than the newest merge of its region by the same
  owner, or bigger than 100 MB.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

MAX_HTML = 100 * 2**20


def _ts(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def check(rows: list[dict]) -> list[dict]:
    now = datetime.now(timezone.utc)
    out = []

    def add(r, color, msg):
        out.append({"node": r["node"], "partition": r["partition"], "color": color, "msg": msg})

    newest_merge: dict[tuple[str, str], datetime] = {}
    for r in rows:
        x = r["extra"]
        if r["node"] == "text.corpus":
            if r["done"]:
                at = _ts(x.get("merged_at")) or _ts(r["freshness_utc"])
                k = (x["owner"], r["partition"].rsplit("/", 1)[1])
                newest_merge[k] = max(newest_merge.get(k, at), at)
            elif any("sin PLAN.tsv" in d for d in r["drift"]):
                add(r, "rojo", "; ".join(r["drift"]))
            elif x.get("run_done") and now - _ts(r["freshness_utc"]) > timedelta(days=2):
                add(r, "rojo", "run .done sin merge después de 2 días")
            elif x.get("run_done"):
                add(r, "amarillo", "; ".join(r["drift"]) or "run .done sin merge")
            else:
                add(r, "amarillo", "run sin .done")
            if x.get("events_log") and not r["rows"]:
                add(r, "rojo", "región con 0 filas")
        elif r["node"] == "text.delta":
            if "owner_conflict" in r["drift"]:
                add(r, "rojo", f"fuente de otro dueño escrita por {x.get('owner')}")
            if x.get("level") == "red":
                add(r, "rojo", f"0 filas {x.get('zero_streak')} corridas seguidas (baseline {x.get('baseline')})")
            elif x.get("level") == "yellow":
                add(r, "amarillo", f"0 filas (baseline {x.get('baseline')})")
            elif x.get("state") == "fail":
                add(r, "amarillo", "fail")
        elif r["node"] == "text.epu" and r["done"]:
            if x.get("counts_utc") and r["freshness_utc"] < x["counts_utc"]:
                add(r, "amarillo", f"epu.csv {r['freshness_utc']} más viejo que counts {x['counts_utc']}")
    for r in rows:
        if r["node"] != "text.dashboard" or not r["done"]:
            continue
        x = r["extra"]
        merged = newest_merge.get((x["owner"], r["partition"].rsplit("/", 1)[1]))
        if merged and _ts(r["freshness_utc"]) < merged:
            add(r, "amarillo", f"dashboard {r['freshness_utc']} más viejo que el merge {merged:%Y-%m-%dT%H:%M:%SZ}")
        if (x.get("bytes") or 0) > MAX_HTML:
            add(r, "amarillo", f"html {x['bytes'] / 2**20:.0f} MB > 100 MB")
    return out
