"""Propose-then-apply retag of `channel:` / `analytical_role:` on source YAMLs.

Successor to the one-shot `audit_source_channels.py`, which backfilled the
field in 2026-06 and hardcoded its own (now stale) copy of the value list.

  python scripts/retag_source_channels.py            # dry run, writes CSV
  python scripts/retag_source_channels.py --apply    # rewrite YAMLs

Idempotent: a file already at its target value is left untouched.

Two passes: a pre-flight parse of every matching manifest (abort before
writing anything if any of them fail to parse), then the write pass. Each
write is re-read and re-parsed to confirm the line-oriented text surgery in
`set_scalar` actually produced the intended value.
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import get_args

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from prices.enrich.schemas import Channel  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIGS_DIR = REPO_ROOT / "src" / "prices" / "configs"
CSV_DIR = REPO_ROOT / "data" / "prices" / "_enrich"

# Cost-of-living survey publishers. Not outlets: modelled averages, no catalog.
SURVEY_SLUGS = {"expatistan", "livingcost", "mylifeelsewhere", "numbeo"}

# slug -> (channel, analytical_role or None to leave unchanged)
RETAG: dict[str, tuple[str | None, str | None]] = {
    slug: (None, "aggregate_proxy") for slug in SURVEY_SLUGS
}


def iter_source_yamls(root: Path):
    for path in sorted(root.rglob("*.yaml")):
        if "_examples" in path.parts:
            continue
        yield path


def load(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def set_scalar(text: str, key: str, value: str | None) -> str:
    """Rewrite `key:` in place, preserving line order. Appends if absent."""
    rendered = "null" if value is None else value
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.startswith(f"{key}:"):
            lines[i] = f"{key}: {rendered}\n"
            return "".join(lines)
    tail = "" if text.endswith("\n") else "\n"
    return text + tail + f"{key}: {rendered}\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Rewrite YAMLs.")
    args = parser.parse_args()

    valid = set(get_args(Channel))
    for slug, (channel, _) in RETAG.items():
        if channel is not None and channel not in valid:
            print(f"FATAL: {slug} -> unknown channel {channel!r}", file=sys.stderr)
            return 2

    matching = [p for p in iter_source_yamls(CONFIGS_DIR) if p.stem in RETAG]

    # Pre-flight: parse every matching manifest before writing anything. A
    # single bad file must abort cleanly, not leave the corpus half-rewritten.
    parsed: dict[Path, dict] = {}
    parse_errors: list[tuple[Path, yaml.YAMLError]] = []
    for path in matching:
        try:
            parsed[path] = load(path)
        except yaml.YAMLError as exc:
            parse_errors.append((path, exc))

    if parse_errors:
        for path, exc in parse_errors:
            print(f"FATAL: failed to parse {path}: {exc}", file=sys.stderr)
        return 2

    run_utc = datetime.now(timezone.utc)
    csv_out = CSV_DIR / f"_channel_retag_{run_utc.strftime('%Y%m%dT%H%M%SZ')}.csv"

    rows, changed = [], 0
    for path in matching:
        data = parsed[path]
        new_channel, new_role = RETAG[path.stem]
        cur_channel = data.get("channel")
        cur_role = data.get("analytical_role")
        if cur_channel == new_channel and (new_role is None or cur_role == new_role):
            continue
        rows.append(
            {
                "run_utc": run_utc.isoformat(),
                "path": str(path.relative_to(REPO_ROOT)),
                "slug": path.stem,
                "channel_from": cur_channel,
                "channel_to": new_channel,
                "role_from": cur_role,
                "role_to": new_role,
            }
        )
        changed += 1
        if args.apply:
            text = path.read_text(encoding="utf-8")
            text = set_scalar(text, "channel", new_channel)
            if new_role is not None:
                text = set_scalar(text, "analytical_role", new_role)
            path.write_text(text, encoding="utf-8")

            verify = load(path)
            if verify.get("channel") != new_channel:
                print(
                    f"FATAL: {path} channel is {verify.get('channel')!r}, "
                    f"expected {new_channel!r}",
                    file=sys.stderr,
                )
                return 2
            if new_role is not None and verify.get("analytical_role") != new_role:
                print(
                    f"FATAL: {path} analytical_role is {verify.get('analytical_role')!r}, "
                    f"expected {new_role!r}",
                    file=sys.stderr,
                )
                return 2

    CSV_DIR.mkdir(parents=True, exist_ok=True)
    with csv_out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "run_utc",
                "path",
                "slug",
                "channel_from",
                "channel_to",
                "role_from",
                "role_to",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    verb = "Applied" if args.apply else "Proposed"
    print(f"{verb} {changed} retags. Detail: {csv_out.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
