"""Suggest a per-model `KNN_SCORE_HARD_MIN` threshold from a labeled set.

Workflow (§8.5):
- Run this script against a validation parquet (one row per query, columns
  `top1_cosine`, `gold_coicop_code`, `predicted_coicop_code`, plus optional
  `model`).
- The tool sweeps thresholds and picks the lowest cosine where self-match
  precision >= --target-precision (default 0.995).
- Prints the threshold, observed precision, sample size at that threshold,
  and a unified diff against the live `config.KNN_SCORE_HARD_MIN` entry.
- NEVER writes config. Paste the suggested value into a config-only PR.
  Preserve this STDOUT in the commit message so `git blame` shows the
  precision target and sample size that justified the value.

Re-running on the same input is deterministic.
"""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_VALIDATION = (
    _REPO_ROOT / "data" / "prices" / "_enrich" / "_validated_warm.parquet"
)
_DEFAULT_CONFIG = _REPO_ROOT / "src" / "prices" / "enrich" / "config.py"


def _load_scores(
    path: Path,
    score_col: str,
    gold_col: str,
    pred_col: str,
    model_filter: str | None,
) -> pd.DataFrame:
    df = pd.read_parquet(path)
    missing = [c for c in (score_col, gold_col, pred_col) if c not in df.columns]
    if missing:
        sys.exit(
            f"{path}: missing required columns {missing}. "
            f"Got: {list(df.columns)[:20]}…"
        )
    if model_filter is not None:
        if "model" not in df.columns:
            sys.exit(
                f"--model {model_filter!r} specified but `model` column absent in {path}"
            )
        df = df[df["model"] == model_filter]
    df = df[df[score_col].notna() & df[gold_col].notna() & df[pred_col].notna()]
    return df.reset_index(drop=True)


def _pick_threshold(
    scores: np.ndarray,
    correct: np.ndarray,
    target_precision: float,
    min_sample: int,
) -> tuple[float | None, float, int]:
    """Walk thresholds from low to high, find lowest cosine where
    precision >= target_precision over a sample of at least `min_sample` rows.
    Returns (threshold, observed_precision, sample_size). Threshold is None
    when no value meets the target.
    """
    order = np.argsort(-scores, kind="stable")  # sort descending
    scores_sorted = scores[order]
    correct_sorted = correct[order]
    cum_correct = np.cumsum(correct_sorted)
    n = np.arange(1, len(scores_sorted) + 1)
    precision = cum_correct / n

    eligible = (n >= min_sample) & (precision >= target_precision)
    if not eligible.any():
        # Pick best-precision row that meets min_sample
        sample_ok = n >= min_sample
        if not sample_ok.any():
            return None, 0.0, 0
        i = int(np.argmax(precision[sample_ok]))
        idx = np.where(sample_ok)[0][i]
        return None, float(precision[idx]), int(n[idx])

    # Lowest threshold = highest n satisfying eligibility = last True in walk order
    idx = int(np.where(eligible)[0][-1])
    return (
        float(scores_sorted[idx]),
        float(precision[idx]),
        int(n[idx]),
    )


def _emit_diff(config_path: Path, model: str, new_value: float) -> str:
    if not config_path.exists():
        return f"# config.py at {config_path} not found; manual update needed\n"
    text = config_path.read_text().splitlines(keepends=True)
    new_text = []
    in_dict = False
    bumped = False
    for line in text:
        stripped = line.strip()
        if stripped.startswith("KNN_SCORE_HARD_MIN") and stripped.endswith("= {"):
            in_dict = True
            new_text.append(line)
            continue
        if in_dict and stripped.startswith("}"):
            in_dict = False
            new_text.append(line)
            continue
        if in_dict and model in line:
            # Replace the literal value preserving indent + comment
            head, sep, tail = line.partition(":")
            if sep:
                value_part = tail.split(",", 1)
                new_text.append(
                    f"{head}: {new_value:.4f},{value_part[1] if len(value_part)>1 else chr(10)}"
                )
                bumped = True
                continue
        new_text.append(line)
    if not bumped:
        return f"# could not locate KNN_SCORE_HARD_MIN[{model!r}] entry in config.py\n"
    return "".join(
        difflib.unified_diff(
            text,
            new_text,
            fromfile=str(config_path),
            tofile=f"{config_path} (suggested)",
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--scores",
        type=Path,
        default=_DEFAULT_VALIDATION,
        help="Parquet of validation rows with top1_cosine + gold + pred columns",
    )
    parser.add_argument("--score-col", default="top1_cosine")
    parser.add_argument("--gold-col", default="gold_coicop_code")
    parser.add_argument("--pred-col", default="predicted_coicop_code")
    parser.add_argument(
        "--model",
        default="intfloat/multilingual-e5-base",
        help="Embedding model key in config.KNN_SCORE_HARD_MIN",
    )
    parser.add_argument("--target-precision", type=float, default=0.995)
    parser.add_argument(
        "--min-sample",
        type=int,
        default=200,
        help="Minimum row count above the threshold (statistical floor)",
    )
    parser.add_argument("--config-py", type=Path, default=_DEFAULT_CONFIG)
    parser.add_argument(
        "--bootstrap-from-tier-c",
        action="store_true",
        help="Treat tier-c predictions as gold (gated; not used in first round)",
    )
    args = parser.parse_args(argv)

    if args.bootstrap_from_tier_c:
        print(
            "# --bootstrap-from-tier-c is gated and not yet implemented",
            file=sys.stderr,
        )
        return 2

    if not args.scores.exists():
        print(f"# scores file not found: {args.scores}", file=sys.stderr)
        return 2

    df = _load_scores(
        args.scores, args.score_col, args.gold_col, args.pred_col, args.model
    )
    if df.empty:
        print(f"# 0 eligible rows in {args.scores}", file=sys.stderr)
        return 2

    scores = df[args.score_col].to_numpy(dtype=float)
    correct = (df[args.gold_col] == df[args.pred_col]).to_numpy(dtype=int)

    threshold, precision, sample_n = _pick_threshold(
        scores, correct, args.target_precision, args.min_sample
    )

    print(f"# Calibration result for model={args.model}")
    print(f"#   target_precision = {args.target_precision}")
    print(f"#   min_sample       = {args.min_sample}")
    print(f"#   corpus           = {args.scores} ({len(df)} eligible rows)")
    if threshold is None:
        print(
            f"#   NO threshold meets target. Best precision={precision:.4f} at n={sample_n}"
        )
        return 1
    print(f"#   suggested        = {threshold:.4f}")
    print(f"#   precision@       = {precision:.4f} over n={sample_n}")
    print()
    print(_emit_diff(args.config_py, args.model, threshold))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
