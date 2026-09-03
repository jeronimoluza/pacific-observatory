"""Common Crawl fetch: on this machine, or staged for an EC2 fleet.

Both run the *same* fetcher. `infra/fetch/ccfetch.py` uploads its output only
when `OUT_BUCKET` is set, so local and fleet are one code path and one env var,
not two implementations that drift.

What differs is throughput and money. A laptop does this at a few records a
second against the public `commoncrawl` bucket; a fleet of small instances in
us-east-1 reads the same bucket for free (requester is the bucket owner) and
finishes in hours. So the fleet is worth having, and starting one is still a
decision a person makes — this stages the run and prints the commands.

**The preflight is the point of this module.** The fleet parses archived HTML
with a bundle of flat modules copied out of `price_scraping/`, and the bundle
list names tiers that may not exist in this checkout. Launching without them
does not fail: it fetches everything, parses a fraction, and reports a low yield
that looks like Common Crawl being thin rather than a missing file. Instances
are keyless and unreachable by design, so that is only visible hours later in a
shipped log. Hence: count the tiers before anything is launched.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
INFRA_FETCH = REPO_ROOT / "infra" / "fetch"
BUNDLE_SCRIPT = INFRA_FETCH / "bundle_parse.py"
PARSE_SRC = REPO_ROOT / "src" / "prices" / "price_scraping"
STAGE_DIR = REPO_ROOT / "data" / "prices" / "_cc_staging"
GUARDRAILS = REPO_ROOT / "infra" / "cc-guardrails.yaml"


def bundle_modules(script: Optional[Path] = None) -> list[str]:
    """The parse modules the fleet bundle expects, read out of the bundler.

    Parsed rather than imported: `bundle_parse.py` reads `sys.argv` at module
    level, so importing it here would pick up whatever argv this process has.
    """
    script = script or BUNDLE_SCRIPT
    if not script.exists():
        return []
    tree = ast.parse(script.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            getattr(t, "id", None) == "FILES" for t in node.targets
        ):
            return [ast.literal_eval(e)[0] for e in node.value.elts]
    return []


def preflight(src: Optional[Path] = None, script: Optional[Path] = None) -> dict:
    """Which parse tiers this checkout can actually ship to a fleet."""
    src = src or PARSE_SRC
    wanted = bundle_modules(script)
    present = [m for m in wanted if (src / m).exists()]
    missing = [m for m in wanted if not (src / m).exists()]
    return {
        "src": src,
        "wanted": len(wanted),
        "present": present,
        "missing": missing,
        "ok": bool(wanted) and not missing,
    }


def report_preflight(check: dict) -> None:
    print(f"[cc-fleet] parse tiers: {len(check['present'])}/{check['wanted']} present")
    for module in check["missing"]:
        print(f"[cc-fleet]   MISSING {module}")


def local_commands(parse_dir: Path, manifest: Path, work: Path) -> list[str]:
    """Run the fleet's own fetcher here. OUT_BUCKET is unset, so ccfetch keeps
    its output on disk instead of streaming it to S3 — same code, no account."""
    return [
        f"python {BUNDLE_SCRIPT} {parse_dir}",
        f"PARSE_DIR={parse_dir} WORK={work} INPUT=manifest "
        f"MANIFEST={manifest} python {INFRA_FETCH / 'ccfetch.py'}",
    ]


def ec2_commands(instances: int) -> list[str]:
    return [
        f"aws cloudformation deploy --template-file {GUARDRAILS} "
        "--stack-name cc-cost-guardrails --capabilities CAPABILITY_NAMED_IAM",
        f"bash {INFRA_FETCH / 'stage_recovery.sh'}",
        f"bash {INFRA_FETCH / 'launch_fleet.sh'} 0 {instances}",
    ]


def run(
    backend: str = "local",
    instances: int = 1,
    manifest: Optional[Path] = None,
    out_dir: Optional[Path] = None,
    allow_partial: bool = False,
) -> dict:
    check = preflight()
    report_preflight(check)
    if not check["ok"] and not allow_partial:
        raise RuntimeError(
            f"{len(check['missing'])} of {check['wanted']} parse tiers are not in "
            "this checkout. A fetch would still run and still cost what a full "
            "one costs, but parse only the tiers that are here and report the "
            "shortfall as a thin crawl. Land the missing modules, or pass "
            "--allow-partial if a degraded run is what you want."
        )

    out_dir = out_dir or STAGE_DIR
    parse_dir = out_dir / "parse"
    if backend == "local":
        commands = local_commands(
            parse_dir, manifest or out_dir / "manifest.jsonl.gz", out_dir / "work"
        )
    elif backend == "ec2":
        commands = ec2_commands(instances)
    else:
        raise ValueError(f"unknown cc backend {backend!r}; have 'local', 'ec2'")

    print(f"[cc-fleet] nothing has been fetched or launched. To run ({backend}):")
    for cmd in commands:
        print(f"    {cmd}")
    return {"backend": backend, "preflight": check, "commands": commands}
