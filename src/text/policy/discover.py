"""Scan a region's news corpus for policy measures the trackers do not record.

Stage 1 of the corpus backfill. Emits the candidate articles that the
extraction pass then reads one at a time; nothing here decides whether an
article reports a measure, only that its headline is worth reading.

The region is an argument, not a constant: the topology in regions.yaml
supplies the country list and countries.yaml supplies the spelling the
workbooks use, so every region runs the same way.

Two gates exist and this runs the per-language one by default.
:mod:`policy_discovery`'s English gate tokenises ``[a-z][a-z0-9-]{2,}``, so a
diacritic ends a token mid-word and an accented headline scores as fragments.
Measured on Niger: the English gate admitted 1 article out of 21,428 and the
language gate admitted 137, and the 137 are real measures -- fuel-shortage
supply operations, cereal destocking, a maintained price-control decree. The
English gate also costs two of the three corpus passes, because it fits term
weights on the corpus before scanning it. Pass --english to add it back for an
anglophone region where it earns its keep.

Usage:
    po text policy-discover --region ssa
    po text policy-discover --region ssa --jobs 8
    po text policy-discover --region eap --english
"""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from core.config import load_countries, load_regions
from text.policy import DATA, DEFAULT_OUT_DIR


def corpus_dirs(
    region: str, only: str | None, data_root: Path = DATA
) -> dict[str, Path]:
    """Map the workbook's country spelling to that country's corpus directory."""
    topology = load_regions().get(region) or {}
    if not topology:
        raise SystemExit(f"unknown region: {region}")
    names = load_countries()

    found: dict[str, Path] = {}
    for sub_key, sub in (topology.get("subregions") or {}).items():
        for slug in sub.get("countries") or []:
            if only and slug != only:
                continue
            path = data_root / region / sub_key / slug
            if not path.is_dir():
                continue
            display = (names.get(slug) or {}).get("name") or slug.replace("_", " ")
            found[display] = path
    return found


def vocab_workbooks() -> list[Path]:
    """Every tracker workbook, both variants, all regions.

    policy_discovery pools these deliberately: the taxonomy is shared and no
    single region has enough labeled rows per Category to learn a vocabulary
    from on its own.
    """
    from text.plotting.trackers import WORKBOOK_ROOT, latest_workbook, workbook_dir

    books = []
    for tracker in ("fuel", "food"):
        root = workbook_dir(WORKBOOK_ROOT, tracker)
        for region in ("eap", "eca", "lac", "menaap", "sar", "ssa"):
            path = latest_workbook(root, region)
            if path is not None:
                books.append(path)
    return books


def scan_country(args: tuple[str, str, float]) -> dict:
    """Run the language gate over one country. Runs in a worker process."""
    country, dir_str, min_score = args
    # Imported here so each worker builds its own automaton cache.
    from text.analysis.policy_discovery_lang import admit
    from text.analysis.policy_retrieval import iter_articles

    rows: list[dict] = []
    n_articles = 0
    coverage: dict[int, int] = {}
    for article in iter_articles(Path(dir_str)):
        n_articles += 1
        date = (article.get("date", "") or "")[:10]
        if len(date) >= 4 and date[:4].isdigit():
            year = int(date[:4])
            coverage[year] = coverage.get(year, 0) + 1
        title = article.get("title", "")
        if not title:
            continue
        verdict = admit(
            title,
            article.get("body", "")[:4000],
            article.get("language", "") or "en",
            min_score=min_score,
        )
        if not verdict:
            continue
        verdict.update(
            {
                "country": country,
                "date": date,
                "url": article.get("url", ""),
                "title": title,
                "source": article.get("source", ""),
            }
        )
        rows.append(verdict)
    rows.sort(key=lambda r: -r.get("score", 0))
    return {
        "country": country,
        "n_articles": n_articles,
        "n_candidates": len(rows),
        "coverage_by_year": dict(sorted(coverage.items())),
        "candidates": rows,
    }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="po text policy-discover")
    ap.add_argument("--region", required=True)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument(
        "--data-root",
        type=Path,
        default=DATA,
        help="corpus root laid out <region>/<subregion>/<country>/<source>/news.csv; "
        "a staged run dir scans only that run's new articles",
    )
    ap.add_argument("--country", help="one slug, for a smoke test")
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--lang-min-score", type=float, default=3.0)
    ap.add_argument(
        "--english",
        action="store_true",
        help="also run policy_discovery's English gate (2 extra corpus passes)",
    )
    ap.add_argument("--min-score", type=float, default=6.0, help="English gate")
    ap.add_argument("--max-df", type=float, default=0.05, help="English gate")
    ap.add_argument("--top-k", type=int, default=60, help="English gate")
    args = ap.parse_args(argv)

    dirs = corpus_dirs(args.region, args.country, args.data_root)
    print(f"region={args.region} countries={len(dirs)} jobs={args.jobs}")
    if not dirs:
        raise SystemExit("no corpus directories found")

    started = time.time()
    results: dict = {"countries": {}}

    payload = [(c, str(p), args.lang_min_score) for c, p in dirs.items()]
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(scan_country, item): item[0] for item in payload}
        for done in as_completed(futures):
            res = done.result()
            results["countries"][res["country"]] = res
            print(
                f"  {res['country']:<28} {res['n_articles']:>9,} articles"
                f" -> {res['n_candidates']:>6,} candidates"
            )

    if args.english:
        from text.analysis import policy_discovery

        eng = policy_discovery.run(
            corpus_dirs=dirs,
            vocab_workbooks=vocab_workbooks(),
            min_score=args.min_score,
            max_df=args.max_df,
            top_k=args.top_k,
        )
        # Merge on url so an article both gates admit is one candidate carrying
        # both verdicts, not two rows for the extraction pass to reconcile.
        for country, block in eng["countries"].items():
            bucket = results["countries"].setdefault(
                country, {"n_articles": 0, "candidates": []}
            )
            by_url = {c.get("url"): c for c in bucket["candidates"] if c.get("url")}
            for row in block.get("candidates", []):
                existing = by_url.get(row.get("url"))
                if existing is not None:
                    existing["english_gate"] = row
                else:
                    bucket["candidates"].append(row)
            bucket["n_candidates"] = len(bucket["candidates"])

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{args.region}" + (f"_{args.country}" if args.country else "")
    out = args.out_dir / f"candidates_{stem}.json"
    out.write_text(json.dumps(results, indent=1))

    total = sum(c["n_candidates"] for c in results["countries"].values())
    articles = sum(c["n_articles"] for c in results["countries"].values())
    print(
        f"\n{articles:,} articles -> {total:,} candidates"
        f" in {time.time() - started:.0f}s"
    )
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
