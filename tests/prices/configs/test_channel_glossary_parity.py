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
ROW = re.compile(r"^\|\s*`([a-z-]+)`\s*\|", re.MULTILINE)
START = "<!-- channel-values:start -->"
END = "<!-- channel-values:end -->"


def _table_values() -> set[str]:
    text = GLOSSARY.read_text(encoding="utf-8")
    assert (
        START in text and END in text
    ), f"missing channel-values markers in {GLOSSARY}"
    block = text.split(START, 1)[1].split(END, 1)[0]
    return set(ROW.findall(block))


def test_glossary_table_matches_channel_literal():
    assert _table_values() == set(get_args(Channel))


def test_every_glossary_row_has_a_discriminating_test():
    """Second column must be non-empty — a value without a test is how the
    taxonomy drifted the first time."""
    text = GLOSSARY.read_text(encoding="utf-8")
    block = text.split(START, 1)[1].split(END, 1)[0]
    for line in block.splitlines():
        if not line.strip().startswith("| `"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        assert len(cells) >= 2, line
        assert cells[1], f"no discriminating test for {cells[0]}"
