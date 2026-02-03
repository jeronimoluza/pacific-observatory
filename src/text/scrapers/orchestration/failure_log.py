"""
Failure logging for Pacific Observatory scraper orchestration.

This module provides functionality to classify and log scraper failures
to a structured JSON file for debugging and analysis.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any


def classify_failure_reason(result: Dict[str, Any]) -> str:
    """
    Classify the reason for a scraper failure.

    Args:
        result: Result dictionary from scraper run with keys:
                - status: str ("success", "failed", "timeout")
                - error_msg: str (optional, error message)

    Returns:
        Classification string: "timeout", "http_error", "parse_error",
                               "process_error", or "unknown"
    """
    # Check for timeout status
    if result.get("status") == "timeout":
        return "timeout"

    # Get error message (case-insensitive)
    error_msg = result.get("error_msg", "").lower()

    # Check for HTTP errors
    http_indicators = ["http", "403", "404", "500", "503"]
    if any(indicator in error_msg for indicator in http_indicators):
        return "http_error"

    # Check for parse errors
    parse_indicators = ["parse", "no articles", "selector", "extraction"]
    if any(indicator in error_msg for indicator in parse_indicators):
        return "parse_error"

    # Check for process errors
    process_indicators = ["exit code"]
    if any(indicator in error_msg for indicator in process_indicators):
        return "process_error"

    # Default to unknown
    return "unknown"


def write_failure_log(results: List[Dict[str, Any]], output_path: Path) -> None:
    """
    Write structured failure log to JSON file.

    Extracts failures from results and writes them to a JSON file with
    classification and metadata.

    Args:
        results: List of result dictionaries from scraper runs
        output_path: Path where JSON file should be written

    The output JSON has the structure:
    {
        "run_timestamp": "2026-01-24T10:30:00.123456",
        "failures": [
            {
                "newspaper": "post_courier",
                "country": "papua_new_guinea",
                "reason": "timeout",
                "duration_seconds": 600,
                "error_msg": "timeout after 600s"
            }
        ]
    }
    """
    # Extract only failures (status in ["failed", "timeout"])
    failures = [r for r in results if r.get("status") in ["failed", "timeout"]]

    # Build failure entries with classification
    failure_entries = []
    for failure in failures:
        entry = {
            "newspaper": failure.get("newspaper"),
            "country": failure.get("country"),
            "reason": classify_failure_reason(failure),
            "duration_seconds": failure.get("duration_seconds"),
            "error_msg": failure.get("error_msg", ""),
        }
        failure_entries.append(entry)

    # Build JSON structure
    log_data = {
        "run_timestamp": datetime.now().isoformat(),
        "failures": failure_entries,
    }

    # Create parent directories if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write to file with proper formatting
    with open(output_path, "w") as f:
        json.dump(log_data, f, indent=2)
