"""Resolve manifest globs: repo code at a git ref or in the working tree, and data paths on disk."""

from __future__ import annotations

import glob
import os
import re
import subprocess
from functools import lru_cache

from graph.manifest import REPO_ROOT


def _glob_regex(pattern: str) -> re.Pattern:
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif pattern.startswith("**", i):
            out, i = out + ".*", i + 2
        elif pattern[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif pattern[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(pattern[i]), i + 1
    return re.compile(out + r"\Z")


def ref_exists(ref: str) -> bool:
    r = subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
                       capture_output=True)
    return r.returncode == 0


@lru_cache(maxsize=None)
def _tree_files(ref: str) -> tuple[str, ...]:
    r = subprocess.run(["git", "-C", str(REPO_ROOT), "ls-tree", "-r", "--name-only", ref],
                       capture_output=True, text=True, check=True)
    return tuple(r.stdout.splitlines())


def repo_files(pattern: str, ref: str | None = None) -> list[str]:
    """Repo-relative files matching `pattern`, at `ref` or in the working tree."""
    if ref:
        rx = _glob_regex(pattern)
        return sorted(f for f in _tree_files(ref) if rx.match(f))
    return sorted(
        str(p.relative_to(REPO_ROOT)) for p in REPO_ROOT.glob(pattern)
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    )


def _braces(path: str) -> list[str]:
    m = re.search(r"\{([^{}]*)\}", path)
    if not m:
        return [path]
    return [x for alt in m.group(1).split(",") for x in _braces(path[:m.start()] + alt + path[m.end():])]


def data_globs(path: str) -> list[str]:
    """A manifest data path as shell globs: `<x>` and `wNN` become `*`, braces expand."""
    path = re.sub(r"<[^<>]*>", "*", path).replace("wNN", "w*")
    return [os.path.expanduser(p) for p in _braces(path)]


def first_match(pattern: str) -> str | None:
    """The first file or dir one glob finds, without listing the rest."""
    return next(glob.iglob(pattern), None)
