"""Fuel publish check: the gate's color per region, plus staleness.

- red: publish blocked by the country-count gate;
- red: no publish (or seeded baseline) newer than 8 days;
- yellow: source failures not listed in known_failures.md, or price jumps
  > 3x the rolling median (marked by publish, never dropped).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

NODE = "fuel.publish"
MAX_AGE = timedelta(days=8)


def check(rows: list[dict]) -> list[dict]:
    now = datetime.now(timezone.utc)
    out = []
    for r in rows:
        if r["node"] != NODE or r["partition"].startswith("_"):
            continue
        part = r["partition"]
        extra = r.get("extra") or {}
        if extra.get("status") == "blocked":
            out.append(
                {
                    "node": NODE,
                    "partition": part,
                    "color": "rojo",
                    "msg": "publish bloqueado: " + "; ".join(r["drift"]),
                }
            )
        fresh = r.get("freshness_utc")
        ts = datetime.fromisoformat(fresh.replace("Z", "+00:00")) if fresh else None
        if ts is None or now - ts > MAX_AGE:
            out.append(
                {
                    "node": NODE,
                    "partition": part,
                    "color": "rojo",
                    "msg": f"sin publish desde {fresh or 'nunca'}",
                }
            )
        new = [d for d in r["drift"] if d.startswith(("new_failures", "qa_jumps"))]
        if new:
            out.append(
                {
                    "node": NODE,
                    "partition": part,
                    "color": "amarillo",
                    "msg": "; ".join(new),
                }
            )
    return out
