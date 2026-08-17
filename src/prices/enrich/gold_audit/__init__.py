"""Gold label-quality audit — find likely-wrong gold labels without relabeling.

The gold set is large enough (50k rows) that a full LLM relabeling pass is both
expensive and scientifically unhelpful: replacing every label makes it
impossible to attribute a downstream metric change to any particular cause.
This package instead ranks gold rows by how likely they are to be *wrong*, using
signals already on disk — out-of-fold classifier predictions, the 21 GB
embedding store, and the original labelers' disagreement record — so that paid
re-adjudication can be aimed at a few thousand rows instead of fifty thousand.

Nothing here mutates gold. Re-adjudication verdicts land as a corrections CSV
that ``classifier.dataset._apply_corrections`` overlays at read time, and only
for rows a human has promoted to ``status="apply"``.

Artifacts are grouped per run under
``data/prices/enrich/_gold_audit/{run_id}/``; ``latest.txt`` points at the most
recent one so the CLI subcommands can chain without repeating the id.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from prices.enrich import config

AUDIT_DIR = config.ENRICH_DIR / "_gold_audit"
LATEST_POINTER = AUDIT_DIR / "latest.txt"

OOF_FILE = "oof.parquet"
NEIGHBORS_FILE = "neighbors.parquet"
SIGNALS_FILE = "signals.parquet"
SUSPECTS_FILE = "suspects.parquet"
EXPERIMENT_FILE = "experiment.json"
BATCH_DIR = "batches"

# Where ingested verdicts land. `dataset._apply_corrections` reads this
# directory, so the audit shares the existing reversible overlay rather than
# inventing a second correction mechanism.
CORRECTIONS_DIR = config.ENRICH_DIR / "gold" / "corrections"


def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_dir(run_id: str) -> Path:
    return AUDIT_DIR / run_id


def ensure_run_dir(run_id: str) -> Path:
    d = run_dir(run_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_runs() -> list[str]:
    if not AUDIT_DIR.exists():
        return []
    return sorted(p.name for p in AUDIT_DIR.iterdir() if p.is_dir())


def read_latest() -> str | None:
    if not LATEST_POINTER.exists():
        return None
    return LATEST_POINTER.read_text().strip() or None


def write_latest(run_id: str) -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_POINTER.write_text(run_id + "\n", encoding="utf-8")


def resolve_run(run_id: str | None) -> str:
    """Explicit id, else the `latest` pointer. Raises when neither exists so a
    subcommand never silently audits a run the caller did not mean."""
    rid = run_id or read_latest()
    if rid is None:
        raise FileNotFoundError(
            "no audit run selected and no latest pointer — "
            "run `prices gold-audit oof` first"
        )
    return rid
