"""Export suspect rows for re-adjudication, and ingest the verdicts.

No LLM is called here. ``export`` writes JSONL batches, an out-of-band labeler
(codex / gemini / opus, same as the original gold rounds) fills in a verdict per
line, and ``ingest`` turns the returned file into a corrections CSV.

The payload deliberately gives the adjudicator more than the original pass got.
The original prompt was ``raw title -> choose COICOP``; here each line also
carries the plausible candidate codes, their COICOP definitions, nearby
high-trust gold examples, and the current label presented as a claim to confirm
or overturn. The point is a *better-informed* second opinion, not a second
sample of the same process.

Ingest never replaces a label on its own. Verdicts land in
``gold/corrections/{run_id}.csv`` with ``status="review"``, and
``classifier.dataset._apply_corrections`` only overlays rows a human has
promoted to ``status="apply"``. Deleting the CSV undoes the round; the
``gold_v5_*`` parquets are never touched.
"""

from __future__ import annotations

import json

import pandas as pd

from prices.enrich import coicop_taxonomy
from prices.enrich.gold_audit import (
    BATCH_DIR,
    CORRECTIONS_DIR,
    ensure_run_dir,
    score,
)

DEFAULT_BATCH_SIZE = 200
N_CANDIDATES = 5
N_EXAMPLES = 5

# Rows the adjudicator sees as trusted exemplars: unanimous originally, and the
# head agrees with them out of fold. Circular if it included suspects.
TRUSTED_MAX_SCORE = 0.0


def _candidates(row: pd.Series) -> list[str]:
    """Current gold, the head's OOF pick, and the neighbourhood majority."""
    out = [row.get("code")]
    for key in ("oof_pred", "neighbor_majority_code", "top1_code"):
        val = row.get(key)
        if isinstance(val, str) and val and val != "None":
            out.append(val)
    seen, uniq = set(), []
    for c in out:
        if isinstance(c, str) and c and c not in seen:
            seen.add(c)
            uniq.append(c)
    return uniq[:N_CANDIDATES]


def _trusted_examples(pool: pd.DataFrame, codes: list[str]) -> dict[str, list[str]]:
    """A few unambiguous gold product names per candidate code."""
    out: dict[str, list[str]] = {}
    for code in codes:
        names = pool.loc[pool["code"] == code, "product_name"].head(N_EXAMPLES)
        out[code] = [str(n) for n in names]
    return out


def _payload(row: pd.Series, pool: pd.DataFrame) -> dict:
    codes = _candidates(row)
    return {
        "gold_row_id": row["gold_row_id"],
        "product_name": str(row["product_name"]),
        "country": row.get("country"),
        "current_gold_code": row.get("code"),
        "candidate_codes": codes,
        "coicop_definitions": coicop_taxonomy.load_coicop_context(frozenset(codes)),
        "trusted_examples": _trusted_examples(pool, codes),
        "why_flagged": row.get("reasons", ""),
        "suspicion_score": float(row.get("suspicion_score", 0.0)),
        "signals": {
            "oof_pred": row.get("oof_pred"),
            "oof_conf": None
            if pd.isna(row.get("oof_conf"))
            else float(row["oof_conf"]),
            "neighbor_majority_code": row.get("neighbor_majority_code"),
            "purity_at_k": None
            if pd.isna(row.get("purity_at_k"))
            else float(row["purity_at_k"]),
            "original_disagreement": row.get("disagreement_type"),
        },
    }


def export(
    run_id: str,
    n: int,
    division: str | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> dict:
    """Write the top-`n` suspects as JSONL batches under the run's ``batches/``."""
    suspects = score.load(run_id)
    trusted = suspects[suspects["suspicion_score"] <= TRUSTED_MAX_SCORE]
    picked = score.top(run_id, n, division=division)

    bdir = ensure_run_dir(run_id) / BATCH_DIR
    bdir.mkdir(parents=True, exist_ok=True)

    files = []
    for start in range(0, len(picked), batch_size):
        chunk = picked.iloc[start : start + batch_size]
        path = bdir / f"batch_{start // batch_size:03d}.jsonl"
        path.write_text(
            "\n".join(
                json.dumps(_payload(r, trusted), ensure_ascii=False)
                for _, r in chunk.iterrows()
            )
            + "\n",
            encoding="utf-8",
        )
        files.append(path.name)

    return {
        "run_id": run_id,
        "division": division,
        "n_requested": n,
        "n_exported": int(len(picked)),
        "n_batches": len(files),
        "batch_dir": str(bdir),
        "files": files,
    }


VERDICT_COLS = {"gold_row_id", "new_code"}


def ingest(run_id: str, verdicts_path: str) -> dict:
    """Turn returned verdicts into ``gold/corrections/{run_id}.csv``.

    Accepts JSONL or CSV with at least ``gold_row_id`` and ``new_code``. Rows
    whose verdict matches the current gold are recorded as ``status="agree"``
    so the round's confirm rate is measurable; only genuine changes are written
    as ``status="review"``, awaiting a human flip to ``apply``."""
    path = str(verdicts_path)
    if path.endswith(".jsonl"):
        v = pd.DataFrame([json.loads(ln) for ln in open(path) if ln.strip()])
    else:
        v = pd.read_csv(path, dtype=str)

    missing = VERDICT_COLS - set(v.columns)
    if missing:
        raise ValueError(f"verdicts file missing columns: {sorted(missing)}")

    current = score.load(run_id)[["gold_row_id", "code", "product_name"]]
    m = v.merge(current, on="gold_row_id", how="left")

    changed = m["new_code"].astype(str) != m["code"].astype(str)
    m["status"] = "agree"
    m.loc[changed, "status"] = "review"
    m["old_code"] = m["code"]
    m["run_id"] = run_id

    CORRECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    out = CORRECTIONS_DIR / f"{run_id}.csv"
    cols = ["gold_row_id", "product_name", "old_code", "new_code", "status", "run_id"]
    m[cols].to_csv(out, index=False)

    return {
        "run_id": run_id,
        "out": str(out),
        "n_verdicts": int(len(m)),
        "n_changed": int(changed.sum()),
        "n_agreed": int((~changed).sum()),
        "confirm_rate": float((~changed).mean()) if len(m) else 0.0,
        "note": "status='review' — flip to 'apply' by hand before retraining",
    }
