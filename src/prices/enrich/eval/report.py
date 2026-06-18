"""Render and persist the gold-eval scorecard."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from prices.enrich.eval.gold import CATEGORICAL_FIELDS
from prices.enrich.eval.metrics import BUCKETS


def _pct(pair) -> str:
    c, t = pair
    return f"{(c / t):.2%}" if t else "n/a"


def _metrics_table(block: dict) -> list[str]:
    lines = ["| metric | correct | total | accuracy |", "|---|---|---|---|"]
    for f in CATEGORICAL_FIELDS:
        c, t = block["fields"][f]
        lines.append(f"| {f} | {c} | {t} | {_pct((c, t))} |")
    c, t = block["unit_value"]
    lines.append(f"| **unit_value** | {c} | {t} | {_pct((c, t))} |")
    return lines


def render(result: dict) -> str:
    overall = result["overall"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    n = overall["n"]
    lines = [
        "# Prices enrich — gold eval",
        "",
        f"- generated: {now}",
        f"- rows: {result.get('n_total', n)} | cache scanned: "
        f"{result.get('n_cache', '?')} | tier_c: {result.get('tier_c', False)}",
        "",
        "## Causal buckets (where the misses live)",
        "",
        "| bucket | count | share |",
        "|---|---|---|",
    ]
    for b in BUCKETS:
        cnt = overall["buckets"][b]
        share = f"{(cnt / n):.2%}" if n else "n/a"
        lines.append(f"| {b} | {cnt} | {share} |")
    reasons = result.get("residual_reasons") or {}
    n_res = result.get("n_residual", sum(reasons.values()))
    lines += [
        "",
        "## Residual reasons (why tier-b didn't fire)",
        "",
        f"- residual rows (tier-b → tier-c): {n_res}",
        "",
        "| escalation_reason | count | share of residual |",
        "|---|---|---|",
    ]
    if reasons:
        for reason, cnt in reasons.items():
            share = f"{(cnt / n_res):.2%}" if n_res else "n/a"
            lines.append(f"| {reason} | {cnt} | {share} |")
    else:
        lines.append("| (none) | 0 | n/a |")

    lines += ["", "## Overall accuracy", ""]
    lines += _metrics_table(overall)

    lines += ["", "## By tier (match_method)", ""]
    for tier, block in result["by_tier"].items():
        lines += [f"### {tier} (n={block['n']})", ""]
        lines += _metrics_table(block)
        lines.append("")

    lines += ["## By labeler_model", ""]
    for lab, block in result["by_labeler"].items():
        lines += [f"### {lab} (n={block['n']})", ""]
        lines += _metrics_table(block)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _summary(result: dict) -> dict:
    return {
        k: result[k]
        for k in (
            "overall",
            "by_tier",
            "by_labeler",
            "n_total",
            "n_cache",
            "tier_c",
            "n_residual",
            "residual_reasons",
        )
        if k in result
    }


def _misses_frame(records: list[dict]) -> pd.DataFrame:
    rows = []
    for r in records:
        if r["bucket"] == "ok":
            continue
        row = {
            "row_id": r["row_id"],
            "country": r["country"],
            "labeler_model": r["labeler_model"],
            "match_method": r["match_method"],
            "bucket": r["bucket"],
            "gold_unit_value": r["gold_unit_value"],
            "pred_unit_value": r["pred_unit_value"],
        }
        for f in CATEGORICAL_FIELDS:
            row[f"{f}_ok"] = r["field_ok"][f]
        rows.append(row)
    return pd.DataFrame(rows)


def write(result: dict, report_md: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "report.md"
    report_path.write_text(report_md)
    (out_dir / "summary.json").write_text(json.dumps(_summary(result), indent=2))
    _misses_frame(result["records"]).to_csv(out_dir / "misses.csv", index=False)
    return report_path
