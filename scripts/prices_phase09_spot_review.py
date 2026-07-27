"""Phase 0.9 — old-vs-new spot-review diff harness for the atomized sub-label store.

Offline, read-only. No LLM, no writes under `src/`. A human RUNS this in Wave 2
to sign off on the atomization output (SC-5b).

Usage:

  python scripts/prices_phase09_spot_review.py \
      --old data/prices/enrich/_audit/_sub_labels_store.pre_atomization.json \
      --new src/prices/enrich/keywords/coicop/_sub_labels_store.json \
      [--out data/prices/enrich/_audit/SPOT-REVIEW.diff.md] [--seed 0]

The reviewer captures `--old` (a snapshot of the pre-atomization store) BEFORE
Wave 1 runs; `--new` defaults to the current/atomized store. In Wave 0 the
harness is exercised as a dry run with `--old == --new` (an all-empty diff).

Sampling (deterministic): >=1 leaf per division 01-15, PLUS unconditionally all
leaves empty in `--old` (the thin-leaf enrichment cases), PLUS unconditionally
the 5 ROADMAP-SC-4 worked-example leaves. The long-slug justification list
(written by `test_id_slug_format`) is rendered when present.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from prices.enrich import config  # noqa: E402

_DEFAULT_NEW = (
    REPO_ROOT
    / "src"
    / "prices"
    / "enrich"
    / "keywords"
    / "coicop"
    / "_sub_labels_store.json"
)
_DEFAULT_OLD = config.ENRICH_DIR / "_audit" / "_sub_labels_store.pre_atomization.json"
_LONG_SLUG_AUDIT = config.ENRICH_DIR / "_audit" / "long_slug_ids.json"

# Mirror of tests/prices/enrich/test_sub_labels_store_invariants.py::_WORKED_EXAMPLE_LEAVES
# (single source of truth lives in the test; imported below when possible).
_WORKED_EXAMPLE_LEAVES_FALLBACK = [
    "01.1.1.2.1",
    "01.1.6.3.1",
    "01.1.2.1.3",
    "01.1.2.2.1",
    "01.1.4.1.2",
]


def _worked_example_leaves() -> list[str]:
    """Import the worked-example leaf set from the test module (single source of
    truth); fall back to a mirrored constant if the import is unavailable."""
    sys.path.insert(0, str(REPO_ROOT / "tests"))
    try:
        from prices.enrich.test_sub_labels_store_invariants import (  # type: ignore
            _WORKED_EXAMPLE_LEAVES,
        )

        return list(_WORKED_EXAMPLE_LEAVES)
    except Exception:
        return list(_WORKED_EXAMPLE_LEAVES_FALLBACK)


def _flatten(store: dict) -> dict[str, list[dict]]:
    """{cc: {leaf_code: [rec...]}} → {leaf_code: [rec...]}."""
    flat: dict[str, list[dict]] = {}
    for cc in store:
        for leaf_code, records in store[cc].items():
            flat[leaf_code] = list(records)
    return flat


def _labels(records: list[dict]) -> list[str]:
    return [rec["label"] for rec in records]


def _division(leaf_code: str) -> str:
    return leaf_code.split(".")[0]


def _select_leaves(
    old_flat: dict[str, list[dict]],
    new_flat: dict[str, list[dict]],
    seed: int,
) -> tuple[list[str], set[str], set[str]]:
    """Return (sorted_leaf_codes, empty_in_old_set, worked_example_set)."""
    all_codes = sorted(set(old_flat) | set(new_flat))
    rng = random.Random(seed)

    # >=1 leaf per division 01-15 (deterministic pick per division).
    by_div: dict[str, list[str]] = {}
    for code in all_codes:
        by_div.setdefault(_division(code), []).append(code)
    per_division = {rng.choice(sorted(codes)) for codes in by_div.values()}

    empty_in_old = {code for code, recs in old_flat.items() if not recs}
    worked = {c for c in _worked_example_leaves() if c in old_flat or c in new_flat}

    selected = sorted(per_division | empty_in_old | worked)
    return selected, empty_in_old, worked


def _render(
    selected: list[str],
    old_flat: dict[str, list[dict]],
    new_flat: dict[str, list[dict]],
    empty_in_old: set[str],
    worked: set[str],
) -> list[str]:
    lines: list[str] = []
    lines.append("# Phase 0.9 sub-label atomization spot-review")
    lines.append("")
    lines.append(
        f"Sampled {len(selected)} leaves: "
        f"{len(empty_in_old)} empty-in-old (enrichment), "
        f"{len(worked)} worked-example, rest division coverage."
    )
    lines.append("")
    for code in selected:
        old_recs = old_flat.get(code, [])
        new_recs = new_flat.get(code, [])
        markers = []
        if code in worked:
            markers.append("WORKED-EXAMPLE")
        if code in empty_in_old:
            markers.append("EMPTY-IN-OLD")
        marker = f" [{', '.join(markers)}]" if markers else ""
        lines.append(f"## {code}{marker}")
        lines.append(f"old items ({len(old_recs)}): {_labels(old_recs)}")
        lines.append(f"new items ({len(new_recs)}): {_labels(new_recs)}")
        lines.append("")
    return lines


def _render_long_slugs() -> list[str]:
    lines: list[str] = []
    lines.append("## Long slugs (>15 chars) needing one-line justification")
    if not _LONG_SLUG_AUDIT.exists():
        lines.append(
            f"(none yet — {_LONG_SLUG_AUDIT.name} appears after test_id_slug_format runs)"
        )
        lines.append("")
        return lines
    slugs = json.loads(_LONG_SLUG_AUDIT.read_text())
    lines.append(f"{len(slugs)} long slugs:")
    for slug in slugs:
        lines.append(f"- {slug}")
    lines.append("")
    return lines


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--old", type=Path, default=_DEFAULT_OLD)
    ap.add_argument("--new", type=Path, default=_DEFAULT_NEW)
    ap.add_argument("--out", type=Path, default=None, help="optional markdown out-path")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    if not args.old.exists():
        ap.error(f"--old not found: {args.old}")
    if not args.new.exists():
        ap.error(f"--new not found: {args.new}")

    old_flat = _flatten(json.loads(args.old.read_text()))
    new_flat = _flatten(json.loads(args.new.read_text()))

    selected, empty_in_old, worked = _select_leaves(old_flat, new_flat, args.seed)
    lines = _render(selected, old_flat, new_flat, empty_in_old, worked)
    lines += _render_long_slugs()

    out = "\n".join(lines)
    print(out)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(out)
        print(f"\nwrote {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
