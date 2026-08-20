"""Compact one-JSON-per-record Common Crawl items into one JSONL per crawl.

The old layout cost an inode and a 4 KB block per ~600-byte record: 28,989
records measured at 17 MB of data but 120 MB on disk. This rewrites an existing
corpus into the layout :mod:`prices.cc_storage` now writes, without re-fetching
anything.

Safety, in order: append what is missing, verify every legacy record is present
in the JSONL by its own hash, and only then unlink the originals. A directory
that fails verification keeps its files and is reported, so a partial or
surprising case costs disk rather than data.

Re-running is safe: records already in the JSONL are not appended twice.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def compact_dir(items: Path, delete_originals: bool) -> Dict[str, int]:
    """Compact one ``.../common_crawl_data/items`` directory."""
    from prices.cc_storage import record_hash

    legacy = sorted(items.glob("*.json"))
    out = {"legacy": len(legacy), "appended": 0, "removed": 0, "verified": 0}
    if not legacy:
        return out

    # Read once, not per file: a source with 30k legacy records would otherwise
    # rescan every JSONL 30k times.
    before = _jsonl_hashes(items)
    by_index: Dict[str, List[str]] = defaultdict(list)
    # path -> hash, so verification can name the file it could not confirm.
    owned: Dict[Path, str] = {}
    for path in legacy:
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # Unreadable, so nothing can confirm it was carried over; leave it
            # on disk rather than delete a record we never managed to read.
            continue
        h = record_hash(rec.get("url", ""), rec.get("cc_timestamp", ""))
        owned[path] = h
        if h in before:
            # Already carried over by an earlier pass. Still owned, so it can
            # be removed, but appending it again would duplicate the row.
            continue
        by_index[rec.get("cc_index") or "unknown"].append(
            json.dumps(rec, ensure_ascii=False)
        )
        before.add(h)

    for index, lines in by_index.items():
        with open(items / f"{index}.jsonl", "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        out["appended"] += len(lines)

    # Verify against what is actually on disk now, not against what we believe
    # we wrote -- the whole point is to not delete on the strength of an
    # assumption.
    after = _jsonl_hashes(items)
    unverified = [p for p, h in owned.items() if h not in after]
    out["verified"] = len(owned) - len(unverified)
    if unverified:
        out["unverified"] = len(unverified)
        return out
    if delete_originals:
        for path in owned:
            try:
                path.unlink()
                out["removed"] += 1
            except OSError:
                pass
    return out


def _jsonl_hashes(items: Path) -> set:
    from prices.cc_storage import iter_jsonl, record_hash

    out = set()
    for path in items.glob("*.jsonl"):
        for rec in iter_jsonl(path):
            out.add(record_hash(rec.get("url", ""), rec.get("cc_timestamp", "")))
    return out


def main(argv: Optional[List[str]] = None) -> int:
    root = _repo_root()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, default=root / "data" / "prices")
    ap.add_argument(
        "--keep-originals",
        action="store_true",
        help="write the JSONL and verify, but do not unlink the per-record files",
    )
    args = ap.parse_args(argv)

    dirs = sorted(args.data.glob("*/*/*/*/common_crawl_data/items"))
    print(f"{len(dirs)} item directories under {args.data}", flush=True)
    totals: Dict[str, int] = defaultdict(int)
    problems = []
    for d in dirs:
        got = compact_dir(d, delete_originals=not args.keep_originals)
        if not got["legacy"]:
            continue
        for k, v in got.items():
            totals[k] += v
        if got.get("unverified"):
            problems.append((d, got))
        print(
            f"  {d.parts[-3]:<28} legacy={got['legacy']:<7} "
            f"appended={got['appended']:<7} removed={got['removed']}",
            flush=True,
        )

    print(
        f"\nlegacy {totals['legacy']:,} | appended {totals['appended']:,} | "
        f"verified {totals['verified']:,} | removed {totals['removed']:,}",
        flush=True,
    )
    for d, got in problems:
        print(f"UNVERIFIED, files kept: {d} ({got['unverified']} records)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
