"""Tests for the protect-data-dirs PreToolUse Bash guard hook."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(".claude/hooks/protect-data-dirs.py")


def _run_hook(command: str):
    payload = json.dumps({"tool_input": {"command": command}})
    out = subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
    )
    return out.stdout.strip()


def test_protect_hook_denies_rm_on_data():
    dec = json.loads(_run_hook("rm -rf data/prices/_enrich/x"))
    assert dec["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_protect_hook_asks_on_mv_data():
    dec = json.loads(_run_hook("mv data/a.csv data/b.csv"))
    assert dec["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_protect_hook_allows_create_and_tmp_rm():
    assert _run_hook("mkdir -p data/prices/_enrich/runs/x") == ""
    assert _run_hook("rm -rf /tmp/scratch/x") == ""


def test_denies_bare_dir_delete():
    for cmd in ("rm -rf data", "rm -rf outputs", "rm -rf ./data", "find data -delete"):
        dec = json.loads(_run_hook(cmd))
        assert dec["hookSpecificOutput"]["permissionDecision"] == "deny", cmd


def test_denies_prefixed_rm():
    for cmd in ("sudo rm -rf data/x", "FOO=bar rm -rf data/x", "env rm -rf data/x"):
        dec = json.loads(_run_hook(cmd))
        assert dec["hookSpecificOutput"]["permissionDecision"] == "deny", cmd


def test_denies_absolute_path():
    dec = json.loads(_run_hook("rm -rf /Users/me/template-repo/data/x"))
    assert dec["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_denies_outputs_and_find_delete():
    assert (
        json.loads(_run_hook("rmdir outputs/y"))["hookSpecificOutput"][
            "permissionDecision"
        ]
        == "deny"
    )
    assert (
        json.loads(_run_hook("unlink data/f"))["hookSpecificOutput"][
            "permissionDecision"
        ]
        == "deny"
    )


def test_allows_lookalikes_and_reads():
    for cmd in (
        "rm -rf data_backup/x",
        "rm mydata/x",
        "cat data/x",
        "grep data/x",
        "mkdir -p data/prices/x",
        "rm -rf /tmp/scratch/x",
        "python run.py prices classify pineapple",
    ):
        assert _run_hook(cmd) == "", cmd
