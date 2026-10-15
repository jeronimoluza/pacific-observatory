"""The vector stores the weekly steps read, from config, and the copy between them.

`copy_vectors` is ~/scratch/w42_score/extract_old.py's loop with the stores and the
destination as arguments: per bucket, the first source holding all three blocks for
a name gives its vectors, and the bucket is written into a new store.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_CONFIG = Path(__file__).with_name("embed_stores.yaml")


@dataclass
class Stores:
    tags: list[str]
    stores: list[tuple[str, Path]]
    week_store: Path
    old_store: Path
    backup_root: Path
    config: Path


def _path(value: str, week: str) -> Path:
    return Path(os.path.expanduser(value.format(week=week)))


def load(week: str, config: Path | None = None) -> Stores:
    config = Path(config or os.environ.get("PRICES_EMBED_STORES") or DEFAULT_CONFIG)
    raw = yaml.safe_load(config.read_text())
    return Stores(
        tags=list(raw["tags"]),
        stores=[(name, _path(p, week)) for name, p in raw["stores"].items()],
        week_store=_path(raw["week_store"], week),
        old_store=_path(raw["old_store"], week),
        backup_root=_path(raw["backup_root"], week),
        config=config,
    )


def require_present(stores: list[tuple[str, Path]]) -> None:
    """A store missing from disk would read as 'no vectors' and inflate the need list."""
    gone = [f"{name} ({root})" for name, root in stores if not root.is_dir()]
    if gone:
        raise SystemExit(f"configured stores missing: {', '.join(gone)}")


def copy_vectors(
    want: dict[int, set[str]],
    sources: list[tuple[str, Path]],
    dst: Path,
    tags: list[str],
) -> tuple[dict[str, int], list[str]]:
    """Copy the vectors of `want` (bucket -> names) from `sources` into the new store `dst`.

    Returns names copied per source, and the names no source holds in all blocks.
    """
    import numpy as np

    from prices.enrich.classifier import embed_store

    if dst.exists():
        raise SystemExit(f"refusing to write into an existing store: {dst}")
    embed_store.STORE_DIR = dst
    t = time.time()
    tot = {s: 0 for s, _ in sources}
    absent: list[str] = []
    for b in sorted(want):
        left = set(want[b])
        store = {tag: {} for tag in tags}
        for s, root in sources:
            if not left:
                break
            found = None
            for tag in tags:
                p = root / tag / f"bucket_{b:03d}.npz"
                if not p.exists():
                    found = set()
                    break
                with np.load(p, allow_pickle=False) as z:
                    ks = set(embed_store.decode_keys(z)) & left
                found = ks if found is None else found & ks
            if not found:
                continue
            for tag in tags:
                with np.load(
                    root / tag / f"bucket_{b:03d}.npz", allow_pickle=False
                ) as z:
                    keys = embed_store.decode_keys(z)
                    idx = [j for j, k in enumerate(keys) if k in found]
                    mat = z["mat"][idx]
                assert np.isfinite(mat).all()
                store[tag].update(zip([keys[j] for j in idx], mat))
            tot[s] += len(found)
            left -= found
        absent += sorted(left)
        if store[tags[0]]:
            for tag in tags:
                embed_store._save_bucket(tag, b, store[tag])
        if b % 32 == 0:
            print(b, tot, "absent", len(absent), f"{time.time() - t:.0f}s", flush=True)
    return tot, absent
