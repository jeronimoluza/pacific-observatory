"""Weekly Common Crawl sweep for newly onboarded sources.

The fleet sweep (2026-09-30) covered every source configured then; after it,
the only sources without archive history are the ones onboarded since. This
sweeps those, unattended, as one stage of the Monday run:

  resolve -> every crawl, each source's own ``archive_prefix``/``archive_path_re``
  fetch   -> WARC ranges over HTTPS (no AWS: the Mac login lasts an hour)
  parse   -> the archived ladder, with the spider's ``parse_html`` hook if it has one
  land    -> ``<source dir>/common_crawl_data/items/cc_weekly_<crawl>.jsonl``

**Keyed by config stem, not spider.** ``common-crawl -s <spider>`` resolves the
scope through ``all_cc_configs``, which keeps the first manifest per spider, so
every ``generic_shopify_configured`` source swept some other shop's host.

**Every miss is kept** (``misses/<crawl>.jsonl.gz``: address + reason). Fetch
failures are retried by the next week's run; parse misses are the input of the
Tuesday parser stage, which writes ``price_scraping/archived_weekly/<source>.py``
and then re-runs only those misses (``--retry-misses``).

Landing never overwrites (files open with mode ``x``) and skips captures the
source already holds (``cc_storage.record_hash``), so a retry lands only what it
recovers. ``fetched/<crawl>.done`` marks a finished crawl; a killed run resumes.
"""

from __future__ import annotations

import concurrent.futures as cf
import gzip
import json
import logging
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import click

from prices.cc_config import _spider_class, resolve_cc_indexes
from prices.cc_index import query_prefix
from prices.cc_storage import existing_hashes, record_hash
from prices.cc_weekly_misses import Ban, fetch_raw, sample_misses, check_samples, split_warc
from prices.config import _PRICES_CONFIGS_DIR, PriceSourceConfig, discover_prices_configs

logger = logging.getLogger(__name__)
MISS_REASONS = ("no_extract", "selectors_noprice")
NEEDS_PARSER_MIN = 20  # fetched pages; below this a parser is not worth writing


def load_sources(stems: Iterable[str], data_root: Path) -> Dict[str, dict]:
    """``{stem: {items, currency, scopes, hook}}`` for the named configs."""
    from prices.backfill import _load_spider_parse_html

    want, out = set(stems), {}
    for path in discover_prices_configs():
        if path.stem not in want:
            continue
        cfg = PriceSourceConfig.load(path)
        rel = path.relative_to(_PRICES_CONFIGS_DIR).parent
        currency = (cfg.currency or "").upper()
        if not currency and cfg.spider:
            currency = getattr(_spider_class(cfg.spider), "currency", "") or ""
        scopes = []
        if cfg.spider and cfg.archive_prefix:
            scopes = [(cfg.archive_prefix, cfg.archive_path_re or "")] + [
                (a["prefix"], a.get("path_re") or "") for a in cfg.archive_also or []
            ]
        out[path.stem] = {
            "items": data_root / rel / path.stem / "common_crawl_data" / "items",
            "currency": currency,
            "scopes": scopes,
            "hook": _load_spider_parse_html(cfg.spider) if cfg.spider else None,
        }
    return out


def _read(path: Path):
    with gzip.open(path, "rt") as fh:
        for line in fh:
            yield json.loads(line)


def resolve(sources: Dict[str, dict], crawls: List[str], work: Path) -> Dict[str, Counter]:
    """Write ``work/resolve/<crawl>.jsonl.gz``; return per-source index stats."""
    (work / "resolve").mkdir(parents=True, exist_ok=True)
    stats: Dict[str, Counter] = defaultdict(Counter)
    for crawl in crawls:
        dest = work / "resolve" / f"{crawl}.jsonl.gz"
        if dest.exists():
            for rec in _read(dest):
                stats[rec["source"]]["captures"] += 1
            continue
        t0, n = time.time(), 0
        with gzip.open(f"{dest}.tmp", "wt") as fh:
            for stem, src in sources.items():
                seen = set()
                for prefix, path_re in src["scopes"]:
                    st: Dict[str, int] = {}
                    recs = query_prefix(crawl, prefix, re.compile(path_re or "."), stats=st)
                    stats[stem]["prefix_matched"] += st.get("prefix_matched", 0)
                    stats[stem]["prefix_rejected"] += st.get("prefix_rejected", 0)
                    for r in recs:
                        if (r["url"], r["timestamp"]) in seen:
                            continue
                        seen.add((r["url"], r["timestamp"]))
                        fh.write(json.dumps({"source": stem, **r}) + "\n")
                        stats[stem]["captures"] += 1
                        n += 1
        Path(f"{dest}.tmp").rename(dest)
        logger.info("resolve %s: %d captures, %.0fs", crawl, n, time.time() - t0)
    return stats


def _iso(ts: str) -> Optional[str]:
    try:
        return datetime.strptime(ts, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).isoformat()
    except (ValueError, TypeError):
        return None


class Fetcher:
    """Fetch, parse and land one batch of captures per crawl."""

    def __init__(self, sources: Dict[str, dict], workers: int, stats: Dict[str, Counter]):
        from prices.price_scraping.archived_ladder import decode, parse_rows

        self.decode, self.parse_rows = decode, parse_rows
        self.sources, self.workers, self.stats = sources, workers, stats
        self.have = {s: existing_hashes(src["items"]) for s, src in sources.items()}
        self.parsed: Dict[tuple, tuple] = {}  # (source, digest): same bytes, same rows
        self.ban = {"n": 0}

    def one(self, rec):
        stem, key = rec["source"], (rec["source"], rec.get("digest"))
        if rec.get("digest") and key in self.parsed:
            return rec, *self.parsed[key]
        try:
            raw = fetch_raw(rec, self.ban)
        except Ban:
            raise
        except Exception:
            return rec, None, "fetch_failed"
        headers, body = split_warc(raw)
        if headers is None:
            return rec, None, body
        rows, tier = self.parse_rows(self.decode(headers, body), rec["url"], stem,
                                     hook=self.sources[stem]["hook"])
        self.parsed[key] = (rows or None, tier if rows else "no_extract")
        return rec, *self.parsed[key]

    def run(self, crawl: str, recs: List[dict], misses: Path, tag: str) -> None:
        todo = [r for r in recs if r["source"] in self.sources
                and record_hash(r["url"], r["timestamp"]) not in self.have[r["source"]]]
        out: Dict[str, List[str]] = defaultdict(list)
        missed = []
        with cf.ThreadPoolExecutor(self.workers) as ex:
            for rec, rows, tier in ex.map(self.one, todo):
                stem = rec["source"]
                self.stats[stem][tier if not rows or tier in MISS_REASONS else "parsed"] += 1
                if not rows or tier in MISS_REASONS:
                    missed.append({**{k: rec[k] for k in rec if k != "reason"}, "reason": tier})
                # A price-less row is not landed: landing marks the capture held,
                # and a later parser could then never recover its price on retry.
                for row in rows if rows and tier not in MISS_REASONS else []:
                    row = {"url": rec["url"], **row, "cc_timestamp": rec["timestamp"]}
                    row["scraped_at_utc"] = _iso(rec["timestamp"])
                    if self.sources[stem]["currency"]:
                        row["currency"] = self.sources[stem]["currency"]
                    out[stem].append(json.dumps(row, ensure_ascii=False))
        for stem, lines in out.items():
            items = self.sources[stem]["items"]
            items.mkdir(parents=True, exist_ok=True)
            with open(items / f"cc_{tag}_{crawl}.jsonl", "x", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")
            self.stats[stem]["rows"] += len(lines)
        if missed:
            misses.parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(misses, "wt") as fh:
                fh.write("".join(json.dumps(m) + "\n" for m in missed))
        logger.info("%s %s: %d captures, %d rows, %d misses", tag, crawl, len(todo),
                    sum(len(v) for v in out.values()), len(missed))


def _restat(fetcher: Fetcher, crawl: str, work: Path) -> None:
    """Stats for a crawl a previous (killed) run already finished."""
    miss = work / "misses" / f"{crawl}.jsonl.gz"
    for r in _read(miss) if miss.exists() else []:
        fetcher.stats[r["source"]][r["reason"]] += 1
    for stem, src in fetcher.sources.items():
        f = src["items"] / f"cc_weekly_{crawl}.jsonl"
        if f.exists():
            with f.open("rb") as fh:
                n = sum(1 for line in fh if line.strip())
            fetcher.stats[stem]["rows"] += n
            fetcher.stats[stem]["parsed"] += n


def fetch_land(fetcher: Fetcher, crawls: List[str], work: Path) -> None:
    (work / "fetched").mkdir(parents=True, exist_ok=True)
    for crawl in crawls:
        done = work / "fetched" / f"{crawl}.done"
        if done.exists():
            _restat(fetcher, crawl, work)
            continue
        fetcher.run(crawl, list(_read(work / "resolve" / f"{crawl}.jsonl.gz")),
                    work / "misses" / f"{crawl}.jsonl.gz", "weekly")
        done.touch()


def retry_misses(fetcher: Fetcher, miss_dirs: List[Path], reasons: set, work: Path) -> None:
    """Re-run saved misses; recovered captures land as ``cc_weekly_r<stamp>_<crawl>``."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    by_crawl: Dict[str, List[dict]] = defaultdict(list)
    for d in miss_dirs:
        for f in sorted(d.glob("*.jsonl.gz")):
            by_crawl[f.name[: -len(".jsonl.gz")]] += [
                r for r in _read(f) if r.get("reason") in reasons]
    for crawl, recs in sorted(by_crawl.items()):
        seen, uniq = set(), []
        for r in recs:
            if (r["source"], r["url"], r["timestamp"]) not in seen:
                seen.add((r["source"], r["url"], r["timestamp"]))
                uniq.append(r)
        fetcher.run(crawl, uniq, work / f"misses_r{stamp}" / f"{crawl}.jsonl.gz", f"weekly_r{stamp}")


def write_summary(work: Path, sources: Dict[str, dict], stats: Dict[str, Counter],
                  skipped: Dict[str, str]) -> None:
    cols = ["captures", "prefix_matched", "prefix_rejected", "parsed", "rows",
            "no_extract", "selectors_noprice", "fetch_failed"]
    lines = ["| source | " + " | ".join(cols) + " |", "|---" * (len(cols) + 1) + "|"]
    for stem in sorted(sources, key=lambda s: -stats[s]["rows"]):
        lines.append(f"| {stem} | " + " | ".join(str(stats[stem][c]) for c in cols) + " |")
    need = []
    for stem in sources:
        st = stats[stem]
        miss = sum(st[r] for r in MISS_REASONS)
        fetched = st["parsed"] + miss
        if fetched >= NEEDS_PARSER_MIN and (st["rows"] == 0 or miss > fetched / 2):
            need.append(stem)
    zero = sorted(s for s in sources if not stats[s]["captures"])
    lines += ["", f"Total rows landed: {sum(stats[s]['rows'] for s in sources)}",
              f"Zero captures ({len(zero)}): {', '.join(zero) or '-'}",
              f"Needs a parser ({len(need)}, >half of fetched pages unparsed): "
              f"{', '.join(sorted(need)) or '-'}"]
    lines += [f"- skipped {stem}: {why}" for stem, why in sorted(skipped.items())]
    (work / "cc_summary.md").write_text("\n".join(lines) + "\n")
    (work / "needs_parser.txt").write_text("".join(f"{s}\n" for s in sorted(need)))


def shapes(host: str, crawls: List[str], n: int) -> None:
    """Archived path families under a bare host, for picking prefix + path_re."""
    pick = crawls[:: max(1, len(crawls) // n)][:n]
    fam, example = Counter(), {}
    for crawl in pick:
        for r in query_prefix(crawl, host, re.compile(".")):
            seg = [p for p in r["url"].split("://", 1)[-1].split("?")[0].split("/")[1:] if p][:2]
            k = "/" + "/".join(re.sub(r"\d+", "N", s) if len(s) <= 15 else "*" for s in seg)
            fam[k] += 1
            example.setdefault(k, f"{crawl[8:]} {r['url']}")
    click.echo(f"{host}: {sum(fam.values())} captures in {len(pick)} crawls ({', '.join(pick)})")
    for k, v in fam.most_common(25):
        click.echo(f"{v:7}  {k:40} {example[k]}")


def _stems(path: Path, done: set) -> List[str]:
    stems = []
    for line in path.read_text().splitlines():
        for tok in line.split():
            stem = Path(tok).stem if tok.endswith(".yaml") else tok
            if re.fullmatch(r"[a-z0-9_]+", stem):
                if stem not in done and stem not in stems:
                    stems.append(stem)
                break
    return stems


@click.command("cc-weekly")
@click.option("--sources", "sources_file", type=click.Path(exists=True, path_type=Path),
              help="Config stems or config paths, one per line (first match per line).")
@click.option("--state", type=click.Path(path_type=Path),
              help="Stems already swept; skipped, and appended to after landing.")
@click.option("--data-root", type=click.Path(path_type=Path), help="Prices data root.")
@click.option("--work", type=click.Path(path_type=Path), help="Manifests, misses, summary.")
@click.option("--max-captures", type=int, default=300_000, show_default=True,
              help="Stop after resolve when the total exceeds this (fleet territory).")
@click.option("--workers", type=int, default=2, show_default=True,
              help="HTTPS fetch concurrency; data.commoncrawl.org 403s an address at 6-8.")
@click.option("--dry-run", is_flag=True, help="Resolve and summarise, do not fetch.")
@click.option("--retry-misses", "miss_dirs", multiple=True,
              type=click.Path(exists=True, file_okay=False, path_type=Path),
              help="Re-run the misses saved in DIR (repeatable) instead of sweeping.")
@click.option("--reasons", default="fetch_failed", show_default=True,
              help="Comma list of miss reasons --retry-misses re-runs.")
@click.option("--sample-misses", "sample_n", type=int,
              help="Save N miss pages per --sources stem (from the --retry-misses DIRs) "
                   "as HTML under --work, then exit.")
@click.option("--check", "check_dir", type=click.Path(exists=True, path_type=Path),
              help="Parse the HTML samples under DIR with the current ladder, then exit.")
@click.option("--shapes", "shapes_host", help="Print archived path families for HOST, then exit.")
@click.option("--shape-crawls", type=int, default=8, show_default=True)
def cc_weekly_command(sources_file, state, data_root, work, max_captures, workers, dry_run,
                      miss_dirs, reasons, sample_n, check_dir, shapes_host, shape_crawls):
    """Sweep Common Crawl history for newly onboarded sources."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
    if check_dir:
        check_samples(check_dir)
        return
    if shapes_host:
        shapes(shapes_host, resolve_cc_indexes(strict=True), shape_crawls)
        return
    if not (sources_file and data_root and work):
        raise click.UsageError("--sources, --data-root and --work are required")
    work.mkdir(parents=True, exist_ok=True)
    if sample_n or miss_dirs:
        stems = _stems(sources_file, set())
        if sample_n:
            if not miss_dirs:
                raise click.UsageError("--sample-misses needs --retry-misses DIR to read from")
            sample_misses(stems, list(miss_dirs), sample_n, work)
            return
        stats: Dict[str, Counter] = defaultdict(Counter)
        sources = load_sources(stems, data_root)
        retry_misses(Fetcher(sources, workers, stats), list(miss_dirs),
                     set(reasons.split(",")), work)
        rows = sum(stats[s]["rows"] for s in sources)
        click.echo(f"DONE retry {sum(sum(c.values()) for c in stats.values()) - rows} "
                   f"captures, {rows} rows recovered: {dict((s, stats[s]['rows']) for s in sources)}")
        return
    done = set(state.read_text().split()) if state and state.exists() else set()
    stems = _stems(sources_file, done)
    sources = load_sources(stems, data_root)
    skipped = {s: "no config found" for s in stems if s not in sources}
    for stem in [s for s, src in sources.items() if not src["scopes"]]:
        skipped[stem] = "no spider or archive_prefix"
        del sources[stem]
    crawls = resolve_cc_indexes(strict=True)
    click.echo(f"{len(sources)} sources to sweep, {len(skipped)} skipped, {len(crawls)} crawls")
    stats = resolve(sources, crawls, work)
    total = sum(stats[s]["captures"] for s in sources)
    if dry_run or total > max_captures:
        write_summary(work, sources, stats, skipped)
        if total > max_captures:
            raise click.ClickException(
                f"{total} captures > --max-captures {max_captures}: run on the fleet instead")
        return
    fetch_land(Fetcher(sources, workers, stats), crawls, work)
    write_summary(work, sources, stats, skipped)
    if state:
        with state.open("a") as fh:
            fh.write("".join(f"{s}\n" for s in sources))
    click.echo(f"DONE {total} captures, {sum(stats[s]['rows'] for s in sources)} rows "
               f"-> {work / 'cc_summary.md'}")
