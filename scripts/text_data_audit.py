"""Read-only audit of data/text/<region>/<sub>/<country>/<source>/ (news.csv, urls.csv).

Usage (from repo root):
    PYTHONPATH=src python scripts/text_data_audit.py [--region sar] [--data-root data/text] \
        [--out-dir outputs/text/reports/audit] [--jobs 4] [--today 2026-10-07]
    PYTHONPATH=src python scripts/text_data_audit.py --region sar \
        --source-key <sub>/<country>/<source> --write-dedup

Audit mode never writes under the data root. Each news.csv is streamed once (csv module,
constant memory apart from one 8-byte url hash per row). Invalid UTF-8 is read with
surrogateescape, so rows with bad bytes are counted exactly in the same single pass.
Writes data_audit_<region>_<YYYYMMDD>.{md,csv}. --write-dedup writes news.dedup.csv next
to one source's news.csv (first occurrence kept) and never touches the original.
"""

import argparse
import csv
import hashlib
import os
import re
import sys
from array import array
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np

from text.ledger import iter_source_dirs
from text.scrapers.pipelines.storage.csv_writer import CSV_COLUMNS

REGIONS = ["menaap", "sar", "eap", "ssa", "lac", "eca"]
EXPECTED_TOP = {"news.csv", "urls.csv", "failed_urls_seen.csv", "failed", "metadata"}
MIN_DATE = date(1990, 1, 1)
BAD_BYTES = re.compile("[\udc80-\udcff]")
MAX_EX = 5
MAX_LINES = 5

METRICS = [
    "news_rows",
    "dup_urls",
    "dup_rows",
    "bad_rows",
    "missing_cols",
    "extra_cols",
    "empty_body",
    "date_unparseable",
    "date_future",
    "date_pre1990",
    "date_min",
    "date_max",
    "bad_utf8_rows",
    "urls_rows",
    "urls_dup",
    "drift_news_not_in_urls",
    "appledouble",
    "unexpected_files",
]
# metrics whose non-zero value counts as an issue (dates / row counts excluded)
ISSUE = [
    m for m in METRICS if m not in ("news_rows", "urls_rows", "date_min", "date_max")
]


def h8(url):
    return int.from_bytes(
        hashlib.blake2b(url.encode("utf-8", "surrogateescape"), digest_size=8).digest(),
        "big",
    )


def parse_date(s):
    s = s.strip()
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(s).date()
    except ValueError:
        return None


def audit_source(task):
    """Worker: returns (key, metrics dict, examples dict, array of unique url hashes)."""
    key, source_dir, today = task
    source_dir = Path(source_dir)
    m = dict.fromkeys(METRICS, 0)
    m["date_min"] = m["date_max"] = ""
    ex = {}
    future_limit = today + timedelta(days=1)
    csv.field_size_limit(2**31 - 1)

    # 3. files
    apple, unexpected = [], []
    for root, _dirs, files in os.walk(source_dir):
        for f in files:
            if f.startswith("._"):
                apple.append(str((Path(root) / f).relative_to(source_dir)))
    for p in sorted(source_dir.iterdir()):
        if p.name not in EXPECTED_TOP:
            unexpected.append(p.name)
    m["appledouble"], m["unexpected_files"] = len(apple), len(unexpected)
    ex["appledouble"] = apple[:MAX_EX]
    ex["unexpected_files"] = unexpected[:MAX_EX]

    # 2a. urls.csv
    url_set, have_urls = set(), (source_dir / "urls.csv").exists()
    if have_urls:
        seen = 0
        with open(
            source_dir / "urls.csv",
            newline="",
            encoding="utf-8",
            errors="surrogateescape",
        ) as f:
            rd = csv.reader(f)
            head = next(rd, [])
            col = head.index("url") if "url" in head else 0
            try:
                for row in rd:
                    if len(row) > col:
                        seen += 1
                        url_set.add(h8(row[col].strip()))
            except csv.Error as e:
                ex["urls_csv_error"] = str(e)[:100]
        m["urls_rows"] = seen
        m["urls_dup"] = seen - len(url_set)

    # 1. news.csv
    hashes = array("Q")
    news = source_dir / "news.csv"
    if news.exists():
        seen_h = set()
        dup_h = set()
        dup_ex, bad_lines, bad_utf8_lines, drift = [], [], [], 0
        dmin = dmax = None
        with open(news, newline="", encoding="utf-8", errors="surrogateescape") as f:
            rd = csv.reader(f)
            head = next(rd, [])
            m["missing_cols"] = len(set(CSV_COLUMNS) - set(head))
            m["extra_cols"] = len(set(head) - set(CSV_COLUMNS))
            ex["header_missing"] = sorted(set(CSV_COLUMNS) - set(head))
            ex["header_extra"] = sorted(set(head) - set(CSV_COLUMNS))
            iu = head.index("url") if "url" in head else None
            ib = head.index("body") if "body" in head else None
            idt = head.index("date") if "date" in head else None
            n = len(head)
            while True:
                try:
                    row = next(rd)
                except StopIteration:
                    break
                except csv.Error:
                    m["bad_rows"] += 1
                    if len(bad_lines) < MAX_LINES:
                        bad_lines.append(rd.line_num)
                    continue
                m["news_rows"] += 1
                if len(row) != n:
                    m["bad_rows"] += 1
                    if len(bad_lines) < MAX_LINES:
                        bad_lines.append(rd.line_num)
                    continue
                if any(BAD_BYTES.search(c) for c in row):
                    m["bad_utf8_rows"] += 1
                    if len(bad_utf8_lines) < MAX_LINES:
                        bad_utf8_lines.append(rd.line_num)
                # Rows without a url (pina's 2025-11-05 bulk import) are
                # distinct articles, not duplicates of one another.
                if iu is not None and row[iu].strip():
                    u = row[iu].strip()
                    h = h8(u)
                    if h in seen_h:
                        m["dup_rows"] += 1
                        dup_h.add(h)
                        if len(dup_ex) < MAX_EX and u not in dup_ex:
                            dup_ex.append(u)
                    else:
                        seen_h.add(h)
                        hashes.append(h)
                        if have_urls and h not in url_set:
                            drift += 1
                if ib is not None and not row[ib].strip():
                    m["empty_body"] += 1
                if idt is not None:
                    d = parse_date(row[idt])
                    if d is None:
                        m["date_unparseable"] += 1
                    elif d > future_limit:
                        m["date_future"] += 1
                    elif d < MIN_DATE:
                        m["date_pre1990"] += 1
                    else:
                        dmin = d if dmin is None or d < dmin else dmin
                        dmax = d if dmax is None or d > dmax else dmax
        m["dup_urls"] = len(dup_h)
        m["drift_news_not_in_urls"] = drift if have_urls else 0
        m["date_min"] = dmin.isoformat() if dmin else ""
        m["date_max"] = dmax.isoformat() if dmax else ""
        ex["dup_urls"] = dup_ex
        ex["bad_rows"] = bad_lines
        ex["bad_utf8_rows"] = bad_utf8_lines
    return key, m, ex, hashes


def shared_groups(region_results):
    """Cross-source: hashes present in 2+ sources. Returns (count, [(hash, [keys])] top)."""
    keys = [k for k, _h in region_results]
    arrs = [np.frombuffer(h, dtype=np.uint64) for _k, h in region_results if len(h)]
    ids = [i for i, (_k, h) in enumerate(region_results) if len(h)]
    if not arrs:
        return 0, []
    allh = np.concatenate(arrs)
    allid = np.concatenate(
        [np.full(len(a), i, dtype=np.int32) for a, i in zip(arrs, ids)]
    )
    order = np.argsort(allh, kind="stable")
    allh, allid = allh[order], allid[order]
    starts = np.flatnonzero(np.r_[True, allh[1:] != allh[:-1]])
    counts = np.diff(np.r_[starts, len(allh)])
    multi = np.flatnonzero(counts > 1)
    top = (
        multi[np.argsort(-counts[multi], kind="stable")][:MAX_EX] if len(multi) else []
    )
    out = [
        (
            int(allh[starts[g]]),
            [keys[i] for i in allid[starts[g] : starts[g] + counts[g]]],
        )
        for g in top
    ]
    return len(multi), out


def resolve_urls(source_dir, wanted):
    """Second pass over url column only: hash -> url for the wanted hashes."""
    found = {}
    csv.field_size_limit(2**31 - 1)
    with open(
        source_dir / "news.csv", newline="", encoding="utf-8", errors="surrogateescape"
    ) as f:
        rd = csv.reader(f)
        head = next(rd, [])
        iu = head.index("url")
        for row in rd:
            if len(row) == len(head):
                h = h8(row[iu].strip())
                if h in wanted and h not in found:
                    found[h] = row[iu].strip()
                    if len(found) == len(wanted):
                        break
    return found


def write_dedup(source_dir):
    """Write news.dedup.csv next to news.csv, keeping the first row per url."""
    src, dst = source_dir / "news.csv", source_dir / "news.dedup.csv"
    if dst.exists():
        sys.exit(f"refusing to overwrite existing {dst}")
    csv.field_size_limit(2**31 - 1)
    with open(src, "rb") as f:
        first = f.readline()
    term = "\r\n" if first.endswith(b"\r\n") else "\n"
    seen, kept, dropped = set(), 0, 0
    with (
        open(src, newline="", encoding="utf-8", errors="surrogateescape") as fi,
        open(dst, "w", newline="", encoding="utf-8", errors="surrogateescape") as fo,
    ):
        rd = csv.reader(fi)
        wr = csv.writer(fo, lineterminator=term)
        head = next(rd)
        wr.writerow(head)
        iu = head.index("url")
        for row in rd:
            if len(row) == len(head):
                # No url: only an identical whole row counts as a duplicate.
                h = h8(row[iu].strip() or "\x00" + "\x1f".join(row))
                if h in seen:
                    dropped += 1
                    continue
                seen.add(h)
            wr.writerow(row)
            kept += 1
    print(
        f"original: {src}\ndedup:    {dst}\nkept {kept} rows, dropped {dropped}",
        flush=True,
    )


def md_table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return out


def audit_region(region, args, today, stamp):
    region_dir = Path(args.data_root) / region
    tasks = [(k, str(d), today) for k, d in iter_source_dirs(region_dir)]
    print(f"[{region}] {len(tasks)} sources", flush=True)
    results, hashes = {}, []
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        for i, (key, m, ex, h) in enumerate(pool.map(audit_source, tasks), 1):
            results[key] = (m, ex)
            hashes.append((key, h))
            flag = [k for k in ISSUE if m[k]]
            print(
                f"[{region}] {i}/{len(tasks)} {key}: rows={m['news_rows']} issues={','.join(flag) or '-'}",
                flush=True,
            )
    n_shared, top = shared_groups(hashes)
    shared_per_source = Counter()
    top_out = []
    for h, ks in top:
        wanted = {h}
        url = ""
        for k in ks:
            url = resolve_urls(region_dir / k, wanted).get(h, "")
            if url:
                break
        top_out.append((url, ks))
    # per-source shared count: count hashes shared, attributed to each source holding them
    if n_shared:
        allh = {k: np.frombuffer(h, dtype=np.uint64) for k, h in hashes if len(h)}
        cat = np.concatenate(list(allh.values()))
        uniq, cnt = np.unique(cat, return_counts=True)
        multi = uniq[cnt > 1]
        for k, a in allh.items():
            shared_per_source[k] = int(np.isin(a, multi).sum())

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base = out_dir / f"data_audit_{region}_{stamp}"
    cols = ["region", "source_key"] + METRICS + ["shared_urls_other_sources"]
    with open(base.with_suffix(".csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for k, (m, _ex) in results.items():
            w.writerow([region, k] + [m[x] for x in METRICS] + [shared_per_source[k]])

    tot = {
        x: sum(results[k][0][x] for k in results)
        for x in METRICS
        if x not in ("date_min", "date_max")
    }
    bad = {
        k: v
        for k, v in results.items()
        if any(v[0][x] for x in ISSUE) or shared_per_source[k]
    }
    lines = [
        f"# Text data audit: {region} ({stamp})",
        "",
        f"Data root `{args.data_root}`, sources {len(results)}, with issues {len(bad)}, "
        f"news rows {tot['news_rows']}, run date {today}.",
        "",
        "## Totals",
        "",
        *md_table(["metric", "total"], [(x, tot[x]) for x in ISSUE]),
        f"| urls_in_2plus_sources | {n_shared} |",
        "",
        "## Sources with issues",
        "",
    ]
    short = [x for x in ISSUE]
    rows = []
    for k, (m, _ex) in bad.items():
        rows.append(
            [k, m["news_rows"]]
            + [m[x] or "" for x in short]
            + [shared_per_source[k] or ""]
        )
    lines += (
        md_table(["source", "rows"] + short + ["shared"], rows) if rows else ["None."]
    )
    lines += ["", "## Examples", ""]
    for k, (m, ex) in bad.items():
        parts = []
        for name in (
            "dup_urls",
            "bad_rows",
            "bad_utf8_rows",
            "appledouble",
            "unexpected_files",
            "header_missing",
            "header_extra",
        ):
            if ex.get(name):
                parts.append(f"{name}: {ex[name]}")
        if m["date_min"] or m["date_max"]:
            parts.append(f"valid dates {m['date_min']}..{m['date_max']}")
        if parts:
            lines += [f"- `{k}`", *[f"  - {p}" for p in parts]]
    lines += ["", "## Same url in 2+ sources (top groups)", ""]
    if top_out:
        lines += [
            f"- {url or '(url not resolved)'}: {', '.join(ks)}" for url, ks in top_out
        ]
    else:
        lines.append("None.")
    lines += ["", "## Dedup plan (not applied)", ""]
    plan = [(k, v[0]["dup_rows"]) for k, v in results.items() if v[0]["dup_rows"]]
    if plan:
        lines += md_table(
            ["file", "rows to drop", "command"],
            [
                (
                    f"{args.data_root}/{region}/{k}/news.csv",
                    n,
                    f"`PYTHONPATH=src python scripts/text_data_audit.py --region {region} --source-key {k} --write-dedup`",
                )
                for k, n in plan
            ],
        )
    else:
        lines.append("No duplicate news urls.")
    base.with_suffix(".md").write_text("\n".join(lines) + "\n")
    print(f"[{region}] wrote {base}.md / .csv", flush=True)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--region", choices=REGIONS)
    ap.add_argument("--data-root", default="data/text")
    ap.add_argument("--out-dir", default="outputs/text/reports/audit")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--today", default=None, help="run date, default today")
    ap.add_argument("--source-key", help="<sub>/<country>/<source>, for --write-dedup")
    ap.add_argument("--write-dedup", action="store_true")
    args = ap.parse_args()

    if args.write_dedup:
        if not (args.region and args.source_key):
            sys.exit(
                "--write-dedup needs --region and --source-key (one source at a time)"
            )
        source_dir = Path(args.data_root) / args.region / args.source_key
        if not (source_dir / "news.csv").is_file():
            sys.exit(f"no news.csv in {source_dir}")
        write_dedup(source_dir)
        return

    today = date.fromisoformat(args.today) if args.today else date.today()
    stamp = today.strftime("%Y%m%d")
    for region in [args.region] if args.region else REGIONS:
        if not (Path(args.data_root) / region).is_dir():
            print(f"[{region}] missing, skipped", flush=True)
            continue
        audit_region(region, args, today, stamp)


if __name__ == "__main__":
    main()
