"""mangusa_cw: a trailing "(N pieces)" is a wholesale CASE size.

The measure describes ONE unit and N of them ship together, so N multiplies the
denominator. Verified per source, never assumed -- mangusa_cw is a bulk
hypermarket whose own manifest records the convention ("Unoli Canola oil 2ltr
(6 pieces)" at XCG 84.10, which is a case price: as a lone 2L bottle it implies
~$23/L of canola oil). Volume basis was already right (volume always
multiplies); mass basis was not, and priced a whole case as one piece. Other
sources using the same phrasing are NOT patched -- the identical words mean
pack-total at some of them, so each one has to be checked on its own evidence.

Moved here from `stages/extraction.py`'s `_PIECE_IS_CASE_SOURCES` allowlist on
2026-09-24; measured then at 2,903 of 16,214 rows, all mass basis.
"""

from prices.enrich.regex_patterns.types import Intent, SourcePatch

PATCH = SourcePatch(
    flags=frozenset({"piece_is_case"}),
    intent={
        "piece_is_case": Intent(
            why="bulk hypermarket: '(N pieces)' is a case of N units, priced as the case",
            expect="mass -> mass",  # multiplier 1 -> N, count N -> 1, is_multipack
            rows=2903,
            examples=(
                "Kraft 3 cheese macaroni  cheese 206 gr (24 pieces)",
                "Cereal Vanillewafels 90gr (12 pieces)",
                "Badia Badia onion flakes 1lb (6 pieces)",
                "Prego Traditional italiaan sauce 24oz (12 pieces)",
            ),
        ),
    },
)
