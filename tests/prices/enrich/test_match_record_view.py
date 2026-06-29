"""Renderer tests for the read-only §9 match-record view.

Build a tiny synthetic set of the three long-format logs in ``tmp_path`` (the
real ``data/`` dir is never touched), then assert the plain-text renderers show
the accepted/suppressed/residual trace and the summary header, and that the
Click command degrades gracefully (prints the produce hint, exits 0) when the
logs are absent.
"""

from __future__ import annotations

import pandas as pd
from click.testing import CliRunner

from prices.enrich.match_record_view import (
    PRODUCE_CMD,
    match_record_command,
    render_row,
    render_summary,
)


def _write_synthetic_logs(log_dir):
    log_dir.mkdir(parents=True, exist_ok=True)
    match = pd.DataFrame(
        [
            # row 1: accepted pack candidate + a suppressed appliance candidate
            {
                "row_id": 1,
                "regex_id": "pack_lang",
                "matched_text": "6x500ml",
                "start_char": 10,
                "end_char": 17,
                "capture_groups_json": "{}",
                "candidate_amount": 500.0,
                "candidate_unit": "ml",
                "candidate_multiplier": 6.0,
                "candidate_basis": "volume",
                "accepted": True,
                "suppressed": False,
                "suppression_reason": None,
                "priority_rank": 3,
            },
            {
                "row_id": 1,
                "regex_id": "appliance_cap",
                "matched_text": "99L",
                "start_char": 20,
                "end_char": 23,
                "capture_groups_json": "{}",
                "candidate_amount": 99.0,
                "candidate_unit": "l",
                "candidate_multiplier": None,
                "candidate_basis": "volume",
                "accepted": False,
                "suppressed": True,
                "suppression_reason": "appliance_capacity",
                "priority_rank": None,
            },
            # row 2: plain item, nothing accepted from a candidate
            {
                "row_id": 2,
                "regex_id": "secondary_vu",
                "matched_text": None,
                "start_char": None,
                "end_char": None,
                "capture_groups_json": "{}",
                "candidate_amount": None,
                "candidate_unit": None,
                "candidate_multiplier": None,
                "candidate_basis": None,
                "accepted": False,
                "suppressed": False,
                "suppression_reason": None,
                "priority_rank": None,
            },
        ]
    )
    suppression = pd.DataFrame(
        [
            {
                "row_id": 1,
                "suppressed_text": "99L",
                "suppression_type": "match",
                "suppression_reason": "appliance_capacity",
                "start_char": 20,
                "end_char": 23,
                "regex_id": "appliance_cap",
            }
        ]
    )
    residual = pd.DataFrame(
        [
            {
                "row_id": 1,
                "raw_name": "Soda 6x500ml 99L Fridge",
                "working_name": "Soda 6x500ml 99L Fridge",
                "residual_text": "Soda 99L Fridge",
                "accepted_source": "pack_lang",
                "priority_rank": 3,
            },
            {
                "row_id": 2,
                "raw_name": "Plain Item",
                "working_name": "Plain Item",
                "residual_text": "Plain Item",
                "accepted_source": "item",
                "priority_rank": 9,
            },
        ]
    )
    match.to_parquet(log_dir / "match_log_long.parquet", index=False)
    suppression.to_parquet(log_dir / "suppression_log.parquet", index=False)
    residual.to_parquet(log_dir / "residual_log.parquet", index=False)
    return match, suppression, residual


def test_render_row_shows_accept_suppress_residual(tmp_path):
    match, suppression, residual = _write_synthetic_logs(tmp_path / "logs")
    match_rows = match[match["row_id"] == 1].to_dict("records")
    suppression_rows = suppression[suppression["row_id"] == 1].to_dict("records")
    residual_row = residual[residual["row_id"] == 1].to_dict("records")[0]

    out = render_row(1, match_rows, suppression_rows, residual_row)

    assert "ROW 1" in out
    # accepted marker + its rank + matched_text + span
    assert "✓" in out
    assert "rank3" in out
    assert "6x500ml" in out
    assert "[10:17]" in out
    # suppressed candidate marker + non-null reason
    assert "✗" in out
    assert "SUPPRESSED" in out
    assert "appliance_capacity" in out
    # residual text from the residual_log row
    assert "Soda 99L Fridge" in out


def test_render_summary_counts(tmp_path):
    match, suppression, residual = _write_synthetic_logs(tmp_path / "logs")
    out = render_summary(match, suppression, residual)

    # row count
    assert "rows: 2" in out
    # accepted basis distribution line present
    assert "accepted candidate_basis:" in out
    assert "volume" in out
    # suppression_reason value-count line
    assert "appliance_capacity" in out
    # accepted_source distribution
    assert "pack_lang" in out


def test_missing_logs_prints_produce_hint(tmp_path):
    runner = CliRunner()
    result = runner.invoke(match_record_command, ["--dir", str(tmp_path / "none")])
    assert result.exit_code == 0
    assert "PRICES_MATCH_RECORD=1" in result.output
    assert PRODUCE_CMD in result.output
