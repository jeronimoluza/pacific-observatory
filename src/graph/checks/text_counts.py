"""Checks on ``text.counts`` per country (TX-14), from ``<cache>/<region>/<sub>/<country>/source_counts.params.json``.

- red (T23): a key repeated in ``source_set``;
- red (T26): ``tails[key].n_rows`` != rows of the news.csv files that map to that key
  (``text.analysis.baseline.source_key_for_news_path``) under ``--corpus-root``;
- yellow: ``tails[key].last_date`` older than the newest ledger watermark of those dirs
  (``<state-dir>/<region>.sqlite``, opened read-only);
- yellow: ``keyword_hashes`` != the hash of the current keyword packs (fingerprint).

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


def news_rows(news_csv: Path) -> int:
    import pandas as pd

    return sum(len(c) for c in pd.read_csv(news_csv, usecols=["date"], dtype=str, chunksize=500_000))


def corpus_by_key(country_dir: Path) -> dict[str, list[Path]]:
    from text.analysis.baseline import source_key_for_news_path

    out: dict[str, list[Path]] = {}
    for p in sorted(country_dir.glob("*/news.csv")):
        if not p.parent.name.startswith("."):
            out.setdefault(source_key_for_news_path(p), []).append(p)
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
             "corpus_rows": None, "dirs": None, "watermark": None}
        country_dir = corpus_root / region / sub / country
        if country_dir.is_dir():
            by_key = corpus_by_key(country_dir)
            r["dirs"] = {k: [p.parent.name for p in ps] for k, ps in by_key.items()}
            r["corpus_rows"] = {k: sum(news_rows(p) for p in ps) for k, ps in by_key.items()}
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
    """Registry hook: no observer reads the counts cache, so this points at the direct run."""
    if not any(r["node"] == NODE for r in rows):
        return []
    return [{"node": NODE, "partition": "*", "color": "amarillo",
             "msg": "T23/T26 requieren corrida directa: python -m graph.checks.text_counts"}]


def evaluate(rows: list[dict]) -> list[dict]:
    out = []

    def add(r, color, msg):
        out.append({"node": NODE, "partition": f"{r['region']}/{r['country']}", "color": color, "msg": msg})

    for r in rows:
        if r["dup_keys"]:
            add(r, "rojo", "T23 claves repetidas en source_set: "
                + ", ".join(f"{k} x{n}" for k, n in sorted(r["dup_keys"].items())))
        if r["corpus_rows"] is not None:
            for k, t in sorted(r["tails"].items()):
                have = r["corpus_rows"].get(k, 0)
                if t.get("n_rows") != have:
                    add(r, "rojo", f"T26 {k}: tails.n_rows {t.get('n_rows'):,} != news.csv {have:,} "
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
