"""GLOSSARY channel table must match the Channel Literal exactly."""
from __future__ import annotations

import re
from pathlib import Path
from typing import get_args

from prices.enrich.schemas import Channel

GLOSSARY = (
    Path(__file__).resolve().parents[3] / "src" / "prices" / "docs" / "GLOSSARY.md"
)

# Rows look like: | `supermarket` | General grocery chain … | coles_au … |
# Only lowercase-with-hyphens values parse. That invariant is enforced
# separately by test_channel_literal_is_non_empty_lowercase_strings; if it ever
# relaxes, widen this class or rows will silently fail to parse.
ROW = re.compile(r"^\|\s*`([a-z-]+)`\s*\|", re.MULTILINE)
START = "<!-- channel-values:start -->"
END = "<!-- channel-values:end -->"


def _channel_block() -> str:
    text = GLOSSARY.read_text(encoding="utf-8")
    assert (
        START in text and END in text
    ), f"missing channel-values markers in {GLOSSARY}"
    return text.split(START, 1)[1].split(END, 1)[0]


def _table_values() -> set[str]:
    return set(ROW.findall(_channel_block()))


def test_glossary_table_matches_channel_literal():
    assert _table_values() == set(get_args(Channel))


def test_every_glossary_row_has_a_discriminating_test():
    """Second column must be non-empty — a value without a test is how the
    taxonomy drifted the first time."""
    for line in _channel_block().splitlines():
        if not line.strip().startswith("| `"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        assert len(cells) >= 2, line
        assert cells[1], f"no discriminating test for {cells[0]}"
