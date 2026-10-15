"""What the step runners share: how a step re-enters Python, and how a runner reports.

A step's argv is `env PYTHONPATH=<repo>/src python -u -m prices.weekly.steps.<step> ...`,
so the runner imports the same tree the unit was started from and its stdout reaches
the step log unbuffered. Phases a runner wants in their own process (to hand memory
back between them) re-enter the same module with `--phase`.
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

from prices.weekly.status import Status
from prices.weekly.step import REPO_ROOT, Context

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def py_argv(module: str, ctx: Context, *extra: str) -> list[str]:
    argv = [
        "env",
        f"PYTHONPATH={REPO_ROOT / 'src'}",
        sys.executable,
        "-u",
        "-m",
        module,
        "--week",
        ctx.week,
        "--week-dir",
        str(ctx.week_dir),
    ]
    if ctx.countries:
        argv += ["--countries", ",".join(ctx.countries)]
    return argv + list(extra)


def parser(step: str) -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog=f"prices.weekly.steps.{step}")
    ap.add_argument("--week", required=True)
    ap.add_argument("--week-dir", type=Path, required=True)
    ap.add_argument(
        "--countries", default=None, help="comma-separated slugs; omit for all"
    )
    ap.add_argument("--phase", default=None)
    return ap


def countries(arg: str | None) -> list[str] | None:
    return [c for c in arg.split(",") if c] if arg else None


def setup_logging() -> None:
    # `prices process` never configures logging, so its logger.info lines went
    # nowhere and the W42 enrich logs stayed at 0 bytes.
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, stream=sys.stdout)


def say(status: Status, msg: str) -> None:
    print(f"== {msg}", flush=True)
    status.event(msg)


def phase(
    module: str,
    args: argparse.Namespace,
    name: str,
    *extra: str,
    env: dict | None = None,
) -> int:
    """Run one phase of this runner in its own process; its output joins the step log."""
    argv = ["env", f"PYTHONPATH={REPO_ROOT / 'src'}"]
    argv += [f"{k}={v}" for k, v in (env or {}).items()]
    argv += [
        sys.executable,
        "-u",
        "-m",
        module,
        "--week",
        args.week,
        "--week-dir",
        str(args.week_dir),
    ]
    if args.countries:
        argv += ["--countries", args.countries]
    argv += ["--phase", name, *extra]
    sys.stdout.flush()
    return subprocess.run(argv, cwd=REPO_ROOT).returncode


def prepared_files(prepared_dir: Path, wanted: list[str] | None) -> list[Path]:
    files = sorted(prepared_dir.glob("*/*/*.parquet"))
    if wanted is None:
        return files
    keep = set(wanted)
    return [p for p in files if p.stem in keep]
