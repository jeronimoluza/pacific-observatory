"""What a prediction shard was scored under, so reuse can be checked.

A shard is only comparable to a new one if everything that determines a score is
the same. The shard *path* already carries the bundle version — shards live in
``_hierlex_pred/<scorer.version>/`` — and that is the only field enforced today.
Everything else is unguarded, and the embed recipe is the part that moves:

    gpu_bf16        3 blocks  2560+4096+1024 = 7680  weights 2.0 / 4.0 / 0.5
    gpu_bf16_equal  4 blocks  1024+2560+4096+1024 = 8704  all weights 1.0
    qwen3_concat    3 blocks  tags 0p6b / 4b / 8b_q8, locally encoded

The ensemble is selected from an env var at import, and the preset name appears
nowhere in the shard path. So flipping ``CLASSIFIER_EMBED_PRESET``, or editing a
single weight in place, silently reuses shards scored in a different vector
space — and between the first two presets the tags are not even the same
directories in the store, so it is a different *set of files*, not a rescaling.

The failure is quiet rather than loud. A dimension mismatch would raise inside
``scorer.score``, but only for a bucket that actually gets scored; a cached
bucket returns before any matrix is built. A run therefore completes with some
buckets from one vector space and some from another.

That was survivable while any new name in a bucket forced a full rescore, which
eventually rewrote shards. Scoring only the missing pairs removes that accidental
safety net and makes a stale shard permanent, so the fingerprint has to come in
with it, not after it.

**On mismatch the shard is discarded and the bucket rescored. It is never
appended to.**
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from prices.enrich import config

# Bumped when the fingerprint's own meaning changes, so old sidecars are treated
# as mismatches rather than being read under new rules.
FORMAT = 2


def _blocks() -> list[list]:
    """The ensemble as ordered, comparable primitives.

    Order is part of the identity: blocks are hstacked in this order, so the same
    set in a different order is a different vector space.

    `dim` is optional. Locally-encoded presets (`qwen3_concat`) declare no `dim`
    — it comes from the encoder — where store-backed presets do. A missing dim
    must compare equal to a missing dim, not raise.
    """
    return [
        [
            str(b["tag"]),
            None if b.get("dim") is None else int(b["dim"]),
            float(b.get("weight", 1.0)),
            str(b.get("backend", "")),
        ]
        for b in config.CLASSIFIER_EMBED_ENSEMBLE
    ]


def _bundle_sha(version: str | None) -> str | None:
    """One hash over the bundle's own per-artifact sha256 list.

    Reads the manifest, not the 1.1 GB of weights. Guards the case the path
    cannot: a bundle rebuilt and reshipped under the same `method_version`.
    """
    try:
        from prices.enrich.hierlex import package
    except ImportError:
        return None
    try:
        arts = package.manifest(package.resolve(version))["artifacts"]
    except Exception:
        return None
    h = hashlib.sha256()
    for a in sorted(arts, key=lambda a: a["path"]):
        h.update(f"{a['path']}:{a['sha256']}\n".encode())
    return h.hexdigest()


def current(version: str | None = None, scorer_version: str | None = None) -> dict:
    """Everything that determines a score, as a comparable dict."""
    blocks = _blocks()
    dims = [b[1] for b in blocks]
    return {
        "format": FORMAT,
        # First, because it is the field that does the work.
        "blocks": blocks,
        # Redundant with `blocks`, and kept so a mismatch reads as a number
        # rather than having to be inferred from a tuple diff.
        "dim": None if any(d is None for d in dims) else sum(dims),
        "scorer_version": scorer_version,
        "bundle_sha": _bundle_sha(version),
    }


def sidecar_path(part: Path) -> Path:
    return part.with_suffix(part.suffix + ".fingerprint.json")


def write(part: Path, fp: dict) -> None:
    """Stamp a shard. Written after the shard, so a crash between the two leaves
    an unstamped shard — which reads as a mismatch and is rescored."""
    sidecar_path(part).write_text(json.dumps(fp, sort_keys=True), encoding="utf-8")


def read(part: Path) -> dict | None:
    p = sidecar_path(part)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def matches(part: Path, fp: dict) -> bool:
    """True only for a shard stamped with exactly this fingerprint.

    An unstamped shard is a mismatch. Every shard written before this existed is
    unstamped, and there is no way to tell which recipe produced it — treating
    that as "probably fine" is the assumption this module exists to remove.
    """
    return read(part) == fp


def stamp_unstamped(shard_dir: Path, fp: dict) -> list[Path]:
    """Adopt pre-existing shards into a fingerprint. Returns what it stamped.

    **This asserts something the code cannot check.** Shards written before
    fingerprinting carry no record of the recipe that produced them, so this is
    an operator saying "I know what these were scored under". Wrong, it is
    exactly the silent stale-shard failure the rest of this module prevents, and
    it will not announce itself.

    Use it only when the recipe is established from outside the shard — the
    bundle's own `model_manifest.json` naming `embedding_recipe` and
    `embedding_specs`, matched block for block against
    `config.CLASSIFIER_EMBED_ENSEMBLE`. When in doubt, rescore instead: a
    full pass costs hours, and a mixed-vector-space corpus costs a rerun of
    everything downstream plus the time spent trusting it.

    Already-stamped shards are left alone, including ones stamped differently —
    a disagreeing stamp is evidence, not noise to overwrite.
    """
    stamped = []
    for part in sorted(shard_dir.glob("pred_*.parquet")):
        if read(part) is None:
            write(part, fp)
            stamped.append(part)
    return stamped
