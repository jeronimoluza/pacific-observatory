"""Policy corpus pipeline: discover -> slice -> shard -> (agents) -> assemble -> merge."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA = REPO_ROOT / "data" / "text"
# Output lands beside the extended workbooks, not the canonical ones: the
# backfill is kept parallel to the tracker it is derived from until adopted.
DEFAULT_OUT_DIR = DATA / "policy_tracker_extended"
