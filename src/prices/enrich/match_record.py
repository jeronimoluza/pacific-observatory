"""Tier (a) side-channel match-event recorder (§9 long-format logs).

A module-level sink, **default OFF**. Every `record_*` entry point returns
immediately when recording is off (or no row is active), so `extract()` /
`decide()` keep their signatures and a production run pays zero hot-loop cost
(CONTEXT.md LOCKED "Recorder data path" — observation, never mutation).

When armed (`enable()` + per-row `begin_row()`), the recorder buffers every
enumerated candidate, the accepted verdict (with its `_RUNGS` priority_rank),
every suppression (with a non-null reason token — the replacement for the
always-None `promo_reason`), and the per-row residual. `flush()` writes the
three §9 tables as parquet under the gitignored `_match_record/` dir.

This module imports only `config` (cheap paths) at top; pandas is imported
lazily in `flush()` so importing the recorder costs nothing on a production run.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from prices.enrich.config import ENRICH_DIR

# The fixed reason vocabulary. `record_suppression` asserts its `reason` is one
# of these tokens — no suppression is recorded without a cause (closes the
# always-None promo_reason defect structurally).
REASON_TOKENS = frozenset(
    {
        "marketing_limit",
        "appliance_capacity",
        "apparel_fabric_weight",
        "servings_portion",
        "total_breakdown",
        "dosage_strength",
    }
)

_MATCH_COLUMNS = (
    "row_id",
    "regex_id",
    "matched_text",
    "start_char",
    "end_char",
    "capture_groups_json",
    "candidate_amount",
    "candidate_unit",
    "candidate_multiplier",
    "candidate_basis",
    "accepted",
    "suppressed",
    "suppression_reason",
    "priority_rank",
)
_SUPPRESSION_COLUMNS = (
    "row_id",
    "suppressed_text",
    "suppression_type",
    "suppression_reason",
    "start_char",
    "end_char",
    "regex_id",
)
_RESIDUAL_COLUMNS = (
    "row_id",
    "raw_name",
    "working_name",
    "residual_text",
    "accepted_source",
    "priority_rank",
)

# Columns whose values arrive mixed (raw regex strings on synthetic candidates,
# floats/ints elsewhere) and so must be coerced to a single numeric dtype before
# parquet serialization, which cannot infer a type for a mixed str/float column.
_NUMERIC_COLUMNS = frozenset(
    {
        "candidate_amount",
        "candidate_multiplier",
        "priority_rank",
        "start_char",
        "end_char",
    }
)

# Module-level sink (None == OFF) + the current-row buffer (None == no active
# row, so every record_* call no-ops).
_SINK: dict | None = None
_CURRENT: dict | None = None


def is_recording() -> bool:
    return _SINK is not None


def enable(sample_rate: float = 1.0, out_dir=None) -> None:
    """Arm the recorder. `sample_rate` (deterministic on row_id) keeps a sampled
    run reproducible; `out_dir` overrides the default flush target."""
    global _SINK, _CURRENT
    _SINK = {
        "sample_rate": float(sample_rate),
        "out_dir": out_dir,
        "match": [],
        "suppression": [],
        "residual": [],
    }
    _CURRENT = None


def disable() -> None:
    global _SINK, _CURRENT
    _SINK = None
    _CURRENT = None


def reset() -> None:
    """Clear accumulated tables + the current-row buffer. Keeps the sink armed
    (config preserved) when on; a no-op when off."""
    global _CURRENT
    if _SINK is not None:
        _SINK["match"] = []
        _SINK["suppression"] = []
        _SINK["residual"] = []
    _CURRENT = None


def _sampled(row_id, sample_rate: float) -> bool:
    if sample_rate >= 1.0:
        return True
    if sample_rate <= 0.0:
        return False
    h = hashlib.md5(str(row_id).encode("utf-8")).hexdigest()
    return (int(h[:8], 16) / 0xFFFFFFFF) < sample_rate


def begin_row(row_id, raw_name, working_name, country, source) -> None:
    """Apply the sample decision and open a current-row buffer. No-op (leaves
    `_CURRENT=None`, so all record_* drop silently) when off or unsampled."""
    global _CURRENT
    if _SINK is None or not _sampled(row_id, _SINK["sample_rate"]):
        _CURRENT = None
        return
    _CURRENT = {
        "row_id": row_id,
        "raw_name": raw_name,
        "working_name": working_name,
        "country": country,
        "source": source,
        "match": [],
        "accepted_source": None,
        "priority_rank": None,
        "suppressed_ids": {},
    }


def _serializable_groups(groups: dict) -> dict:
    out = {}
    for k, v in groups.items():
        if k == "entry" and isinstance(v, dict):
            out[k] = {kk: v.get(kk) for kk in ("id", "basis", "su")}
        else:
            out[k] = v
    return out


def record_candidate(candidate, *, source_text) -> None:
    """Buffer a §9 match-log event for one enumerated candidate. Reads
    candidate.span / groups; accepted/suppressed/reason/priority_rank are
    reconciled at `end_row`."""
    if _CURRENT is None:
        return
    g = candidate.groups
    span = candidate.span
    if span is not None and source_text is not None:
        start_char, end_char = span[0], span[1]
        matched_text = source_text[start_char:end_char]
    else:
        start_char, end_char, matched_text = None, None, None
    multiplier = g.get("count")
    if multiplier is None:
        multiplier = g.get("outer")
    _CURRENT["match"].append(
        {
            "_source": candidate.source,
            "row_id": _CURRENT["row_id"],
            "regex_id": g.get("regex_id") or candidate.source,
            "matched_text": matched_text,
            "start_char": start_char,
            "end_char": end_char,
            "capture_groups_json": json.dumps(
                _serializable_groups(g), ensure_ascii=False, default=str
            ),
            "candidate_amount": g.get("value"),
            "candidate_unit": g.get("unit"),
            "candidate_multiplier": multiplier,
            "candidate_basis": g.get("basis", candidate.pricing_basis),
        }
    )


def record_accepted(rank, source) -> None:
    """Stamp the winning `_RUNGS` rank + accepted source for this row. The rank
    is the rank decide() passes — never re-derived."""
    if _CURRENT is None:
        return
    _CURRENT["accepted_source"] = source
    _CURRENT["priority_rank"] = rank


def record_suppression(
    *, suppressed_text, span, suppression_type, reason, regex_id
) -> None:
    """Buffer a §9 suppression-log event. `reason` is a REQUIRED non-null token
    from REASON_TOKENS — the field that replaces the always-None promo_reason."""
    if _CURRENT is None:
        return
    assert reason in REASON_TOKENS, f"unknown suppression reason: {reason!r}"
    start_char, end_char = (span[0], span[1]) if span is not None else (None, None)
    _CURRENT.setdefault("suppression", []).append(
        {
            "row_id": _CURRENT["row_id"],
            "suppressed_text": suppressed_text,
            "suppression_type": suppression_type,
            "suppression_reason": reason,
            "start_char": start_char,
            "end_char": end_char,
            "regex_id": regex_id,
        }
    )
    _CURRENT["suppressed_ids"][regex_id] = reason


def _residual_text(accepted_source, working_name):
    if accepted_source is None:
        return working_name
    for ev in _CURRENT["match"]:
        if ev["_source"] != accepted_source:
            continue
        if accepted_source in ("pack_lang", "pack_none"):
            cleaned = json.loads(ev["capture_groups_json"]).get("cleaned")
            return cleaned if cleaned is not None else working_name
        if ev["start_char"] is not None and ev["end_char"] is not None:
            s, e = ev["start_char"], ev["end_char"]
            return (working_name[:s] + working_name[e:]).strip()
        return working_name
    return working_name


def end_row(structural_fields=None) -> None:
    """Reconcile accepted/suppressed flags, compute residual_text, and append the
    buffered events to the three in-memory tables."""
    global _CURRENT
    if _CURRENT is None:
        return
    accepted_source = _CURRENT["accepted_source"]
    rank = _CURRENT["priority_rank"]
    suppressed_ids = _CURRENT["suppressed_ids"]
    for ev in _CURRENT["match"]:
        accepted = ev["_source"] == accepted_source
        reason = None if accepted else suppressed_ids.get(ev["regex_id"])
        final = {k: ev[k] for k in ev if k != "_source"}
        final["accepted"] = accepted
        final["suppressed"] = reason is not None
        final["suppression_reason"] = reason
        final["priority_rank"] = rank if accepted else None
        _SINK["match"].append(final)
    _SINK["suppression"].extend(_CURRENT.get("suppression", []))
    _SINK["residual"].append(
        {
            "row_id": _CURRENT["row_id"],
            "raw_name": _CURRENT["raw_name"],
            "working_name": _CURRENT["working_name"],
            "residual_text": _residual_text(accepted_source, _CURRENT["working_name"]),
            "accepted_source": accepted_source,
            "priority_rank": rank,
        }
    )
    _CURRENT = None


def flush(out_dir=None) -> dict:
    """Write the three §9 parquets (UTC `recorded_at` stamp). Returns the written
    paths. No-op (empty dict) when off."""
    if _SINK is None:
        return {}
    import pandas as pd

    target = Path(out_dir or _SINK["out_dir"] or (ENRICH_DIR / "_match_record"))
    target.mkdir(parents=True, exist_ok=True)
    recorded_at = datetime.now(timezone.utc)

    paths = {}
    for key, rows, cols, fname in (
        ("match", _SINK["match"], _MATCH_COLUMNS, "match_log_long.parquet"),
        (
            "suppression",
            _SINK["suppression"],
            _SUPPRESSION_COLUMNS,
            "suppression_log.parquet",
        ),
        ("residual", _SINK["residual"], _RESIDUAL_COLUMNS, "residual_log.parquet"),
    ):
        df = (
            pd.DataFrame(rows, columns=list(cols))
            if rows
            else pd.DataFrame(columns=list(cols))
        )
        for c in df.columns:
            if c in _NUMERIC_COLUMNS:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        df["recorded_at"] = recorded_at
        path = target / fname
        df.to_parquet(path, index=False)
        paths[key] = path
    return paths
