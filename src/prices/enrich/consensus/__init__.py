"""Consensus layer (W4): witnesses -> tiered gate -> label_store / conflict queue.

Thin adapters over already-shipped machinery (label_store, lexicon, classifier,
tier_b, base_items cascade, price bands, source stamps). Nothing here changes the
behavior of the existing pipeline — the gate only *reads* witnesses and *writes*
label_store / the conflict queue. `prices process` stays byte-identical unless the
`consensus_enabled` settings flag is turned on.
"""

from __future__ import annotations

from pathlib import Path

from prices.enrich import config

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
POLICY_PATH = STATIC_DIR / "consensus_policy.yaml"

QUEUE_DIR = config.ENRICH_DIR / "_queue"
CONFLICTS_PARQUET = QUEUE_DIR / "conflicts.parquet"

REJECT_LABELS = {"__EXCLUDE__", "__OTHER_FORM__"}
