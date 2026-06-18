"""Script-family structural patterns.

Structure (numeral systems, counter grammar, pack-marker shapes) is shared
*within* a script family and differs only in vocabulary *between* languages in
it. Patterns keyed by script (cjk, latin, ...) scale O(scripts) instead of
O(languages). Composition includes script/<script_of(lang)>/* for the row's
language (see _registry._SCRIPT_OF).
"""
