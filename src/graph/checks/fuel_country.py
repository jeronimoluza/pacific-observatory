"""Fuel per-country check over `fuel.country` rows.

- red: the country is built but publishes no rows;
- red: no fuel family is shown any more (last published day older than the
  observer's STALE_DAYS, carry-forward included);
- yellow: a family published on a non-retail price_basis (labelled fallback),
  some families stale, or regime-check alerts for the country.
"""

from __future__ import annotations

NODE = "fuel.country"


def _f(part: str, color: str, msg: str) -> dict:
    return {"node": NODE, "partition": part, "color": color, "msg": msg}


def check(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        if r["node"] != NODE or r["partition"].startswith("_"):
            continue
        part, extra = r["partition"], r.get("extra") or {}
        last, stale = extra.get("last_shown") or {}, extra.get("stale_families") or []
        if not r["done"]:
            out.append(_f(part, "rojo", "sin filas publicadas"))
        elif last and len(stale) == len(last):
            out.append(
                _f(
                    part,
                    "rojo",
                    "ninguna serie vigente, último día publicado: "
                    + ",".join(f"{k}@{v}" for k, v in sorted(last.items())),
                )
            )
        yellow = [
            d
            for d in r["drift"]
            if d.startswith(("fallback", "regime_alerts"))
            or (d.startswith("stale") and len(stale) < len(last))
        ]
        if yellow:
            out.append(_f(part, "amarillo", "; ".join(yellow)))
    return out
