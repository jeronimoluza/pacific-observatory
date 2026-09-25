"""Source-local extraction rules: one `<source>/patch.py` per source.

Each defines `PATCH = SourcePatch(...)` (see `regex_patterns/types.py`); the
composition lives in `dict_view.pattern_set`. A rule here cannot move rows of
any other source. Rules that recur across sources get promoted to shared.
"""
