"""`po fuel watch`: alerts for countries whose fuel prices live in a manual table.

One YAML per country under src/fuel/configs/_watch/. Each run, per country:

- pages: official URLs. `mode: links` hashes the set of matching <a> links (new link ->
  alert, listing it); `mode: urls` does the same for every URL in the raw body (JSON
  APIs, RSS feeds); `mode: text` hashes normalized text lines (new lines -> alert).
  0 matching links is a failure unless `allow_empty: true` (news feeds, home pages),
  and even then the page must still carry some links.
  Normalization drops scripts, styles, comments, dates, times and view counters, plus
  any `ignore` regexes, so cosmetic changes do not alert.
- news: Google News RSS queries. An item alerts once: seen by link OR by normalized
  title, its title must hold a `keywords` term and (when set) a `must` term (country,
  regulator), and be newer than `lookback_days`.
- gpp: GlobalPetrolPrices as a reference only (see watch_gpp.py).
- levels: our table (CSV or _manual YAML); its latest row, or the table's `last_checked`
  date if newer, older than `stale_months` -> amarillo.

Every fetch that fails (HTTP error, parse error, matching links gone, GPP stale) counts
toward `broken_after`; at that count a rojo "vigilancia rota" goes out, and an info when
it recovers. The first run of a page or query only records a baseline. State per
country (hashes, seen items, GPP anchors, alerts already sent) lives in
<state_dir>/<country>.json, so re-running is idempotent.
"""

from __future__ import annotations

import csv
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

from fuel import watch_gpp
from fuel.watch_pages import _sha, check_news, check_page, fetch, news_url

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = Path(__file__).resolve().parent / "configs" / "_watch"
QUARANTINE = (
    Path(__file__).resolve().parent / "configs" / "_quarantine" / "observations.yaml"
)
STATE_DIR = ROOT / "data" / "fuel" / "_watch"
GPP_DIR = ROOT / "data" / "fuel" / "_reference" / "gpp"


def load_configs(
    country: str | None = None, config_dir: Path = CONFIG_DIR
) -> list[dict]:
    out = []
    for p in sorted(config_dir.glob("*.yaml")):
        cfg = yaml.safe_load(p.read_text())
        if country in (None, cfg["country"]):
            out.append(cfg)  # enabled: false is reported and skipped by the caller
    return out


def _quarantined() -> set[str]:
    if not QUARANTINE.exists():
        return set()
    return {e["observation_hash"] for e in yaml.safe_load(QUARANTINE.read_text()) or []}


def _level_rows(p: Path, cols: dict):
    """(date str, product, price) from a CSV (observations / series) or a _manual YAML table."""
    if p.suffix in (".yaml", ".yml"):
        for r in yaml.safe_load(p.read_text(encoding="utf-8")).get("levels") or []:
            price = r.get("price_local")
            if (
                price is None and r.get("thebe") is not None
            ):  # BERA table: thebe per litre
                price = r["thebe"] / 100.0
            if price is not None and r.get("confidence") != "baja":
                yield str(r["effective"]), r["product"], float(price)
        return
    bad = _quarantined()
    with open(p, newline="") as f:
        for r in csv.DictReader(f):
            if (
                r.get("observation_hash") not in bad
                and r.get(cols["price"])
                and r.get(cols["date"])
            ):
                yield r[cols["date"]], r[cols["product"]], float(r[cols["price"]])


def _last_checked(lv: dict) -> list[date]:
    """`last_checked:` dates of YAML tables: when someone last confirmed the level still holds."""
    out = []
    for p in lv["paths"]:
        p = ROOT / p if not Path(p).is_absolute() else Path(p)
        if p.suffix in (".yaml", ".yml") and p.exists():
            d = yaml.safe_load(p.read_text(encoding="utf-8")).get("last_checked")
            if d:
                out.append(date.fromisoformat(str(d)))
    return out


def latest_levels(lv: dict, today: date) -> dict[str, tuple[date, float]] | None:
    """{product: (date, price)} from our table(s); None when no table file exists."""
    cols = {
        "date": "observation_date",
        "product": "fuel_product",
        "price": "price_local",
        **lv.get("columns", {}),
    }
    paths = [ROOT / p if not Path(p).is_absolute() else Path(p) for p in lv["paths"]]
    paths = [p for p in paths if p.exists()]
    if not paths:
        return None
    out = {}
    for p in paths:
        for ds, product, price in _level_rows(p, cols):
            d = date.fromisoformat(ds[:10])
            if d <= today and (product not in out or d >= out[product][0]):
                out[product] = (d, price)
    return out


def check_levels(cfg: dict, levels, today: date) -> list[tuple[str, str, str]]:
    lv = cfg.get("levels")
    if not lv:
        return []
    if levels is None:
        return [
            (
                "amarillo",
                "levels:missing",
                f"tabla propia no encontrada: {', '.join(lv['paths'])}",
            )
        ]
    if not levels:
        return [
            (
                "amarillo",
                "levels:empty",
                "tabla propia sin filas válidas (vacía o en cuarentena)",
            )
        ]
    last = max([d for d, _ in levels.values()] + _last_checked(lv))
    months = lv.get("stale_months", 3)
    if (today - last).days > months * 30.5:
        return [
            (
                "amarillo",
                f"stale:{last}",
                f"tabla propia vencida: última fila o last_checked {last} (> {months} meses)",
            )
        ]
    return []


def check_gpp(
    cfg: dict, levels, st: dict, ref_dir: Path, today: date, fails: list
) -> list[tuple[str, str, str]]:
    g, out, rows = cfg["gpp"], [], []
    for product, ours_name in g["products"].items():
        wid = f"gpp:{product}"
        url = watch_gpp.URL.format(slug=g["slug"], product=product)
        try:
            when, price = watch_gpp.parse_page(
                fetch(url),
                name=g["name"],
                currency=cfg["currency"],
                max_age_days=g.get("max_age_days", 45),
                today=today,
            )
        except Exception as e:  # noqa: BLE001 - any failure is a broken watch, not a crash
            fails.append((wid, url, f"{type(e).__name__}: {e}"))
            continue
        fails.append((wid, url, None))
        rows.append(
            {
                "gpp_date": when.isoformat(),
                "product": product,
                "price_local": price,
                "currency": cfg["currency"],
                "unit": "liter",
                "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "url": url,
                "reference_only": "true",
            }
        )
        ours = (levels or {}).get(ours_name) if ours_name else None
        out += watch_gpp.compare(
            product, when, price, ours, st.setdefault(product, {}), g
        )
    watch_gpp.append_reference(ref_dir / f"{cfg['country']}.csv", rows)
    return out


# ── orchestration ────────────────────────────────────────────────


def _load_state(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def _save_state(path: Path, st: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, indent=1, sort_keys=True, default=str))
    os.replace(tmp, path)


def _track(
    st: dict, wid: str, url: str, err: str | None, broken_after: int
) -> list[tuple[str, str, str]]:
    """Consecutive-failure counter per watched item -> broken / restored alerts."""
    fails = st.setdefault("fails", {})
    if err is None:
        was = fails.pop(wid, {}).get("n", 0)
        if was >= broken_after:
            st.setdefault("sent", {}).pop(f"broken:{wid}", None)
            return [
                (
                    "info",
                    f"restored:{wid}:{was}",
                    f"vigilancia restaurada: {wid} <{url}> responde de nuevo",
                )
            ]
        return []
    f = fails.setdefault(wid, {"n": 0})
    f["n"], f["last_error"] = f["n"] + 1, err[:200]
    if f["n"] >= broken_after:
        sent = st.setdefault("sent", {})
        for k in [k for k in sent if k.startswith(f"restored:{wid}:")]:
            del sent[k]
        return [
            (
                "rojo",
                f"broken:{wid}",
                f"vigilancia rota: {wid} <{url}> falló {f['n']} veces seguidas ({err[:160]})",
            )
        ]
    return []


def watch_country(
    cfg: dict,
    state_dir: Path = STATE_DIR,
    ref_dir: Path = GPP_DIR,
    now: datetime | None = None,
    save: bool = True,
) -> tuple[list[tuple[str, str]], dict]:
    """Run every check for one country; return (NEW alerts as (severity, message), {watch id: ok|error}).

    save=False (dry run) leaves the state file untouched, so the same alerts come back.
    """
    now = now or datetime.now(timezone.utc)
    today, country = now.date(), cfg["country"]
    path = state_dir / f"{country}.json"
    st = _load_state(path)
    broken_after = cfg.get("broken_after", 3)
    alerts, results = [], []  # results: (watch id, url, error or None)

    for page in cfg.get("pages", []):
        try:
            alerts += check_page(
                page, st.setdefault("pages", {}).setdefault(page["id"], {})
            )
            results.append((f"page:{page['id']}", page["url"], None))
        except Exception as e:  # noqa: BLE001
            results.append(
                (f"page:{page['id']}", page["url"], f"{type(e).__name__}: {e}")
            )
    for q in cfg.get("news", []):
        wid = f"news:{_sha(q['q'])}"
        try:
            alerts += check_news(
                q,
                cfg.get("keywords", []),
                st.setdefault("news", {}).setdefault(q["q"], {}),
                cfg.get("lookback_days", 10),
                now,
                cfg.get("must", []),
            )
            results.append((wid, news_url(q), None))
        except Exception as e:  # noqa: BLE001
            results.append((wid, news_url(q), f"{type(e).__name__}: {e}"))
    levels = latest_levels(cfg["levels"], today) if cfg.get("levels") else None
    alerts += check_levels(cfg, levels, today)
    if cfg.get("gpp"):
        alerts += check_gpp(
            cfg, levels, st.setdefault("gpp", {}), ref_dir, today, results
        )
    for wid, url, err in results:
        alerts += _track(st, wid, url, err, broken_after)

    sent, new = st.setdefault("sent", {}), []
    for sev, key, msg in alerts:
        if key not in sent:
            sent[key] = now.isoformat(timespec="seconds")
            new.append((sev, f"fuel-watch {country}: {msg}"))
    st["last_run"] = now.isoformat(timespec="seconds")
    st["last_results"] = {w: (e or "ok") for w, _, e in results}
    if save:
        _save_state(path, st)
    return new, st["last_results"]
