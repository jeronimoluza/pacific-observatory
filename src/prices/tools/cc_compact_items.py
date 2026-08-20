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
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _line_key(rec: dict) -> str:
    """Identity of one stored row.

    NOT the record hash. A page that yields several product rows was stored as
    ``<hash>_0.json``, ``<hash>_1.json``, ... -- every one of them the same URL
    and timestamp but a *different* row. Keying on the record hash collapses
    them into one and silently deletes the rest, which is exactly what an
    earlier version of this tool did to 17,456 rows. The row itself is the only
    honest identity.
    """
    return hashlib.md5(_line(rec).encode("utf-8")).hexdigest()


def _line(rec: dict) -> str:
    return json.dumps(rec, ensure_ascii=False)


def _jsonl_line_keys(items: Path) -> Set[str]:
    from prices.cc_storage import iter_jsonl

    out: Set[str] = set()
    for path in items.glob("*.jsonl"):
        for rec in iter_jsonl(path):
            out.add(_line_key(rec))
    return out


def compact_dir(items: Path, delete_originals: bool) -> Dict[str, int]:
    """Compact one ``.../common_crawl_data/items`` directory."""
    legacy = sorted(items.glob("*.json"))
    out = {"legacy": len(legacy), "appended": 0, "removed": 0, "verified": 0}
    if not legacy:
        return out

    # Read once, not per file: a source with 30k legacy records would otherwise
    # rescan every JSONL 30k times.
    present = _jsonl_line_keys(items)
    by_index: Dict[str, List[str]] = defaultdict(list)
    # path -> key, so verification can name the file it could not confirm.
    owned: Dict[Path, str] = {}
    for path in legacy:
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # Unreadable, so nothing can confirm it was carried over; leave it
            # on disk rather than delete a record we never managed to read.
            continue
        key = _line_key(rec)
        owned[path] = key
        if key in present:
            # Carried over by an earlier pass, or a byte-identical duplicate.
            continue
        by_index[rec.get("cc_index") or "unknown"].append(_line(rec))
        present.add(key)

    for index, lines in by_index.items():
        with open(items / f"{index}.jsonl", "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        out["appended"] += len(lines)

    # Verify against what is actually on disk now, not against what we believe
    # we wrote -- the whole point is to not delete on the strength of an
    # assumption.
    after = _jsonl_line_keys(items)
    unverified = [p for p, k in owned.items() if k not in after]
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
