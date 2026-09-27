"""Thai gram abbreviation "N ก." -> "N กรัม" (the spelled-out surface).

Thai retail writes กรัม (gram) as a bare "ก." with a mandatory period
("แครกเกอร์ไส้แยมสับปะรด400ก.", "ผงปรุงรส 400 ก. X 20"). A bare "ก" cannot be a
units.yaml surface: it is the first letter of กรัม, กิโล and กก, and a
following period does not end a `\\b` word. Rewriting it to กรัม before any
pattern runs lets the shared measure and pack productions read it, so
"400 ก. X 20" keeps its case count, which the makro_pro-only extra_unit this
replaces could not (the extra-unit rung always emits multiplier 1).

Guards, from that makro_pro pattern: no letter, digit, dot or comma before the
number, and no Thai letter right after the period (the start of a longer word).
The no-period form ("350 ก 1") is left alone: it is ambiguous with a following
count or serial number. A space follows the rewrite: "100ก.1X14" and
"800ก.X10X1ลัง" glue the next token to the period, and กรัม glued to it has no
word boundary for the measure to end on.
"""

from __future__ import annotations

import re

_TH_G_ABBR_RE = re.compile(r"(?<![A-Za-z0-9.,])(\d+(?:\.\d+)?)\s*ก\.(?![ก-๏])")


def expand_thai_gram(name: str) -> str:
    """Rewrite `<n> ก.` -> `<n> กรัม `."""
    return _TH_G_ABBR_RE.sub(r"\1 กรัม ", name)
