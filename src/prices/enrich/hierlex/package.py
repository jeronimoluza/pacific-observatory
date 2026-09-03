"""Locate, verify and import a frozen HierLex-Select bundle.

The bundle directory is the unit of versioning: the weights, the scorer source
that reads them, and the `lib/` + `data/` the scorer imports all ship together
and are never edited here. Version-locking the weights alone is the failure the
package's own DEPLOYMENT_NOTES warns about — the mini-batch softmax it freezes is
not solver-identical to the historical LBFGS fit, so a weight file read by the
wrong code silently produces a different operating point rather than an error.

`load_module` imports the vendored scorer as a module so its functions can be
called directly. Reimplementing them here would defeat the whole exercise: the
measured 98% precision belongs to that code path, not to a paraphrase of it.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType

from prices.enrich import config

PACKAGE_ROOT = config.PRODUCTS_INPUT_PARQUET.parent / "_models" / "hierlex"
SCORER_REL = Path("scripts") / "score_hierlex_select.py"
MANIFEST_REL = Path("models") / "model_manifest.json"


def available() -> list[str]:
    if not PACKAGE_ROOT.exists():
        return []
    return sorted(p.name for p in PACKAGE_ROOT.iterdir() if (p / MANIFEST_REL).exists())


def resolve(version: str | None = None) -> Path:
    """Bundle directory for `version`, or the newest installed one."""
    names = available()
    if not names:
        raise FileNotFoundError(
            f"no HierLex bundle installed under {PACKAGE_ROOT} — unzip the "
            "implementation package there (see `prices hierlex verify`)"
        )
    if version is None:
        version = names[-1]
    if version not in names:
        raise FileNotFoundError(
            f"HierLex bundle {version!r} not installed; have: {', '.join(names)}"
        )
    return PACKAGE_ROOT / version


def manifest(pkg: Path) -> dict:
    return json.loads((pkg / MANIFEST_REL).read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def verify(pkg: Path) -> list[str]:
    """Artifact paths whose bytes disagree with the shipped manifest.

    An empty list is the go signal. A non-empty one means the bundle was
    truncated, partially synced, or edited — all of which invalidate the
    validation evidence attached to it.
    """
    problems: list[str] = []
    for art in manifest(pkg)["artifacts"]:
        p = pkg / art["path"]
        if not p.exists():
            problems.append(f"{art['path']}: missing")
        elif p.stat().st_size != int(art["bytes"]):
            problems.append(
                f"{art['path']}: {p.stat().st_size} bytes, manifest says {art['bytes']}"
            )
        elif _sha256(p) != art["sha256"]:
            problems.append(f"{art['path']}: sha256 mismatch")
    return problems


def load_module(pkg: Path) -> ModuleType:
    """Import the bundle's own scorer source.

    The scorer does `sys.path.insert(0, PACKAGE)` at import time so its `lib`
    and `data` siblings resolve — which is why it is imported from the installed
    bundle rather than copied into `src/`. Loading it twice from two bundles in
    one process would leave the second bundle's `lib` shadowed by the first, so
    a process scores one version.
    """
    path = pkg / SCORER_REL
    spec = importlib.util.spec_from_file_location(f"hierlex_scorer_{pkg.name}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot import HierLex scorer from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
