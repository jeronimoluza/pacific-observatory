"""Checks on ``text.counts`` per country (TX-14), from ``<cache>/<region>/<sub>/<country>/source_counts.params.json``.

- red (T23): a key repeated in ``source_set``, or two corpus folders with one key
  (``text.source_keys``; folders retired by its alias map are left out, like the build does);
- red (T26): ``tails[key].n_rows`` != rows of the news.csv files that map to that key
  under ``--corpus-root``, one row per url (the build's dedup);
- red: a folder whose news.csv has more rows than unique urls;
- red: a folder without a config whose urls are (>= 95%) inside a folder with a config
  of the same country, and not in the alias map (a renamed slug counted twice);
- yellow: ``tails[key].last_date`` older than the newest ledger watermark of those dirs
  (``<state-dir>/<region>.sqlite``, opened read-only);
- yellow: ``keyword_hashes`` != the hash of the current keyword packs (fingerprint).

``graph status`` runs ``check`` over the ``text_build`` rows (params.json only: T23 and the
hash); the corpus checks need ``main``.

The corpus and ledger checks are skipped when their roots are not on this machine
(the cache is on the Mac, the corpus and ledgers on a8).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

NODE = "text.counts"
CACHE_ROOT = Path.home() / "wb/pacificobservatory/repo/template-repo/data/text/cache"
CORPUS_ROOT = Path("/mnt/backup5tb/text-corpus")
STATE_DIR = Path.home() / "text_state"
PARAMS = "source_counts.params.json"


def news_rows(news_csv: Path) -> tuple[int, int, set[str]]:
    """(rows, rows after the build's dedup: one per url, rows without a url all kept, urls)."""
    import pandas as pd

    n = no_url = 0
    urls: set[str] = set()
    for c in pd.read_csv(news_csv, usecols=["url"], dtype=str, chunksize=500_000):
        n += len(c)
        no_url += int(c["url"].isna().sum())
        urls.update(c["url"].dropna())
    return n, len(urls) + no_url, urls


def orphan_copies(country_dir: Path, urls_by_dir: dict[str, set[str]]) -> dict[str, tuple[str, float]]:
    """Folders without a config whose urls are >= 95% inside a folder with one: folder -> (that folder, %)."""
    from text.source_keys import ALIASES_FILE

    configs = ALIASES_FILE.parents[1] / country_dir.relative_to(country_dir.parents[2])
    has_cfg = {y.stem for y in configs.glob("*.yaml")}
    out = {}
    for d, s in urls_by_dir.items():
        if d in has_cfg or not s:
            continue
        best = max(((len(s & a) / len(s), w) for w, a in urls_by_dir.items() if w in has_cfg and a),
                   default=None)
        if best and best[0] >= 0.95:
            out[d] = (best[1], round(100 * best[0], 1))
    return out


def corpus_by_key(country_dir: Path) -> dict[str, list[Path]]:
    from text.source_keys import aliases, source_key

    out: dict[str, list[Path]] = {}
    for p in sorted(country_dir.glob("*/news.csv")):
        if not p.parent.name.startswith(".") and f"{country_dir.name}/{p.parent.name}" not in aliases():
            out.setdefault(source_key(p), []).append(p)
    return out


def current_hashes(params_hashes: dict) -> dict:
    from text.analysis import source_counts

    langs = {lang for per_file in params_hashes.values() for lang in per_file}
    return source_counts.keyword_hash_bundle(Path(source_counts.__file__).parent / "keywords", langs)


def read(cache_root: Path = CACHE_ROOT, corpus_root: Path = CORPUS_ROOT, state_dir: Path = STATE_DIR,
         countries: list[str] | None = None) -> list[dict]:
    from graph.observers.text_ledger import ledger_sources

    ledgers: dict[str, dict] = {}
    rows = []
    for pp in sorted(cache_root.glob(f"*/*/*/{PARAMS}")):
        region, sub, country = pp.parent.relative_to(cache_root).parts
        if countries and country not in countries:
            continue
        params = json.loads(pp.read_text(encoding="utf-8"))
        hashes = params.get("keyword_hashes", {})
        r = {"region": region, "country": country, "params": str(pp),
             "dup_keys": {k: n for k, n in Counter(params.get("source_set", [])).items() if n > 1},
             "tails": params.get("tails", {}), "hash_ok": hashes == current_hashes(hashes),
             "corpus_rows": None, "dirs": None, "dup_url_dirs": {}, "orphans": {}, "watermark": None}
        country_dir = corpus_root / region / sub / country
        if country_dir.is_dir():
            by_key = corpus_by_key(country_dir)
            r["dirs"] = {k: [p.parent.name for p in ps] for k, ps in by_key.items()}
            counted = {p: news_rows(p) for ps in by_key.values() for p in ps}
            r["corpus_rows"] = {k: sum(counted[p][1] for p in ps) for k, ps in by_key.items()}
            r["dup_url_dirs"] = {p.parent.name: n[:2] for p, n in counted.items() if n[0] > n[1]}
            r["orphans"] = orphan_copies(country_dir, {p.parent.name: n[2] for p, n in counted.items()})
            if (state_dir / f"{region}.sqlite").exists():
                if region not in ledgers:
                    ledgers[region] = ledger_sources(region, state_dir)
                r["watermark"] = {
                    k: max((w for p in ps if (w := ledgers[region].get(f"{sub}/{country}/{p.parent.name}",
                                                                       {}).get("watermark"))), default=None)
                    for k, ps in by_key.items()}
        rows.append(r)
    return rows


def check(rows: list[dict]) -> list[dict]:
    """Registry hook over the ``text_build`` observer rows (params.json only): red T23 for a
    key repeated in ``source_set``, yellow for a stale keyword hash. T26, duplicate urls and
    unconfigured copies read every news.csv: they stay in the direct run, named once on "*"."""
    mine = [r for r in rows if r["node"] == NODE and r["done"]]
    if not mine:
        return []
    out = []
    for r in mine:
        dup = r["extra"].get("dup_keys") or {}
        if dup:
            out.append({"node": NODE, "partition": r["partition"], "color": "rojo",
                        "msg": "T23 claves repetidas en source_set: "
                               + ", ".join(f"{k} x{n}" for k, n in sorted(dup.items()))})
        if r["extra"].get("hash_ok") is False:
            out.append({"node": NODE, "partition": r["partition"], "color": "amarillo",
                        "msg": "keyword_hashes != hash actual de los packs"})
    out.append({"node": NODE, "partition": "*", "color": "amarillo",
                "msg": "T26/URLs duplicadas/copias sin config: python -m graph.checks.text_counts --cache-root <cache>"})
    return out


def evaluate(rows: list[dict]) -> list[dict]:
    out = []

    def add(r, color, msg):
        out.append({"node": NODE, "partition": f"{r['region']}/{r['country']}", "color": color, "msg": msg})

    for r in rows:
        if r["dup_keys"]:
            add(r, "rojo", "T23 claves repetidas en source_set: "
                + ", ".join(f"{k} x{n}" for k, n in sorted(r["dup_keys"].items())))
        for k, ds in sorted((r["dirs"] or {}).items()):
            if len(ds) > 1:
                add(r, "rojo", f"T23 {k}: carpetas con la misma clave: {', '.join(ds)}")
        for d, (rows, uniq) in sorted(r["dup_url_dirs"].items()):
            add(r, "rojo", f"URLs duplicadas en {d}: {rows:,} filas > {uniq:,} URLs únicas")
        for d, (w, pct) in sorted(r["orphans"].items()):
            add(r, "rojo", f"carpeta sin config {d}: {pct}% de sus URLs están en {w} (sumarla al mapa de alias)")
        if r["corpus_rows"] is not None:
            for k, t in sorted(r["tails"].items()):
                have = r["corpus_rows"].get(k, 0)
                if t.get("n_rows") != have:
                    add(r, "rojo", f"T26 {k}: tails.n_rows {t.get('n_rows'):,} != news.csv dedup por url {have:,} "
                                   f"({'+'.join(r['dirs'].get(k, [])) or 'sin carpeta'})")
        for k, wm in sorted((r["watermark"] or {}).items()):
            last = r["tails"].get(k, {}).get("last_date")
            if wm and (not last or last < wm):
                add(r, "amarillo", f"{k}: tails.last_date {last} < watermark {wm}")
        if not r["hash_ok"]:
            add(r, "amarillo", "keyword_hashes != hash actual de los packs (el próximo build re-anota todo)")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m graph.checks.text_counts")
    ap.add_argument("--cache-root", type=Path, default=CACHE_ROOT)
    ap.add_argument("--corpus-root", type=Path, default=CORPUS_ROOT)
    ap.add_argument("--state-dir", type=Path, default=STATE_DIR)
    ap.add_argument("--countries", help="comma-separated slugs or a panel name (panel36)")
    a = ap.parse_args(argv)
    countries = None
    if a.countries:
        from prices.weekly.panels import resolve_countries
        countries = resolve_countries(a.countries)
    rows = read(a.cache_root, a.corpus_root, a.state_dir, countries)
    with_corpus = sum(r["corpus_rows"] is not None for r in rows)
    print(f"{len(rows)} países en {a.cache_root}; {with_corpus} con corpus en {a.corpus_root}")
    findings = evaluate(rows)
    for f in findings:
        print(f"{f['color']:<8} {f['node']}  {f['partition']:<36} {f['msg']}")
    by = {c: sum(f["color"] == c for f in findings) for c in ("rojo", "amarillo")}
    print(f"rojo {by['rojo']}; amarillo {by['amarillo']}")
    return 1 if by["rojo"] else 0


if __name__ == "__main__":
    sys.exit(main())
