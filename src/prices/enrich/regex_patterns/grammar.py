"""Compile the locale-invariant grammar classes (M / C / P / B) from the vocab
tables into PackPattern records.

This replaces the hand-enumerated per-surface-form latin patterns: the productions
are fixed (num<->noun adjacency, num x measure, per-unit marker) and only the
vocab tables grow per language. Each latin bucket module now declares an ordered
id list and calls ``build_ids`` — adding a spelling is a table edit, not a new
regex. IDs / kind / lang / role / bucket / script / fixed_count / unit_emit /
pricing_basis_emit are preserved verbatim so composition stays byte-identical
(tests/prices/enrich/test_composition_diff.py) and behaviour is unchanged
(test_extract_equivalence.py).
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from prices.enrich.regex_patterns.types import PackPattern, UnitEmit

_VOCAB = Path(__file__).resolve().parent / "vocab"


def _load(name):
    return yaml.safe_load((_VOCAB / name).read_text(encoding="utf-8"))


_UNITS = _load("units.yaml")
_COUNTS = _load("count_nouns.yaml")
_PB = _load("pack_basis.yaml")

_VAL = r"(?P<value>\d+(?:[.,]\d+)?|[.,]\d+)"  # M value: allows leading-dot decimal
_VAL_P = r"(?P<value>\d+(?:[.,]\d+)?)"  # P value: no leading-dot form
_LB = r"(?<![A-Za-z0-9.])"


def _alt(surfaces):
    return "|".join(sorted(surfaces, key=len, reverse=True))


def _measure_alt(key):
    s = []
    for u in _UNITS[key]:
        s.extend(u["surfaces"])
    return _alt(s)


def _value_unit_regex():
    return re.compile(
        rf"{_LB}{_VAL}\s*(?P<unit>{_measure_alt('measure')})\b", re.IGNORECASE
    )


def _pack_regex(form):
    ua = _measure_alt("pack_measure")
    sep = "[" + "".join(_PB["separators"]) + "]"
    if form == "num_sep_measure":
        return re.compile(
            rf"(?P<count>\d+)\s*{sep}\s*{_VAL_P}\s*(?P<unit>{ua})\b", re.IGNORECASE
        )
    return re.compile(
        rf"{_VAL_P}\s*(?P<unit>{ua})\s*{sep}\s*(?P<count>\d+)\b", re.IGNORECASE
    )


def _count_regex(spec):
    flags = re.IGNORECASE if spec.get("case") == "ci" else 0
    t = spec["template"]
    if t == "regex":
        return re.compile(spec["regex"], flags)
    frag = "|".join(spec["nouns"])
    if t == "num_noun":
        sep = {"required": r"\s+", "glued": r"", "optional": r"\s*"}[
            spec.get("sep", "optional")
        ]
        lb = {"word": r"(?<!\w)", "none": r""}[spec.get("lb", "word")]
        return re.compile(rf"{lb}(?P<count>\d+){sep}(?:{frag})\b", flags)
    if t == "noun_num":
        return re.compile(rf"\b(?:{frag})\s+(?P<count>\d+)\b", flags)
    if t == "fixed":
        return re.compile(rf"\b(?:{frag})\b", flags)
    raise ValueError(t)


# id -> module-level PackPattern metadata (verbatim from the retired modules).
_META = {
    # single_measure (canon M + extra_unit fallbacks)
    "VALUE_UNIT": dict(
        groups=("value", "unit"),
        lang="any",
        role="canonicalization",
        kind="canon",
        bucket="single_measure",
        suppress_window=20,
    ),
    "CENTILITRE": dict(
        groups=("value",),
        lang="any",
        role="extract",
        kind="extra_unit",
        bucket="single_measure",
    ),
    "LITRE_VI": dict(
        groups=("value",),
        lang="any",
        role="extract",
        kind="extra_unit",
        bucket="single_measure",
    ),
    # multipack (canon P + canon count)
    "NUM_X_VALUE_UNIT": dict(
        groups=("count", "value", "unit"),
        lang="any",
        role="canonicalization",
        kind="canon",
        bucket="multipack",
    ),
    "VALUE_UNIT_X_NUM": dict(
        groups=("count", "value", "unit"),
        lang="any",
        role="canonicalization",
        kind="canon",
        bucket="multipack",
    ),
    "NUM_PCS": dict(
        groups=("count",),
        lang="en",
        role="canonicalization",
        kind="canon",
        bucket="multipack",
    ),
    "NUM_PC_GLUED": dict(
        groups=("count",),
        lang="en",
        role="canonicalization",
        kind="canon",
        bucket="multipack",
    ),
    "NUM_X_TRAILING": dict(
        groups=("count",),
        lang="any",
        role="canonicalization",
        kind="canon",
        bucket="multipack",
    ),
    "LOC_VI": dict(
        groups=("count",),
        lang="vi",
        role="canonicalization",
        kind="canon",
        bucket="multipack",
    ),
    "COUNT_UNIT_VI": dict(
        groups=("count",),
        lang="vi",
        role="canonicalization",
        kind="canon",
        bucket="multipack",
    ),
    # per_unit_marker (B)
    "PER_KG_PARENS": dict(
        groups=(),
        lang="en",
        role="extract",
        kind="pricing_basis_marker",
        bucket="per_unit_marker",
    ),
    "PER_KG": dict(
        groups=(),
        lang="en",
        role="extract",
        kind="pricing_basis_marker",
        bucket="per_unit_marker",
    ),
    "PER_LITRE_PARENS": dict(
        groups=(),
        lang="en",
        role="extract",
        kind="pricing_basis_marker",
        bucket="per_unit_marker",
    ),
    "PER_LITRE": dict(
        groups=(),
        lang="en",
        role="extract",
        kind="pricing_basis_marker",
        bucket="per_unit_marker",
    ),
    # count_pack/latin (extra_count, script=latin)
    "EN_CAPS": dict(lang="any", script="latin"),
    "EN_TABLETS": dict(lang="any", script="latin"),
    "EN_SACHETS": dict(lang="any", script="latin"),
    "EN_SHEETS": dict(lang="any", script="latin"),
    "EN_PACK_OF": dict(lang="any", script="latin"),
    "EN_N_PACK": dict(lang="any", script="latin"),
    "EN_N_INDIVIDUAL_PACK": dict(lang="any", script="latin"),
    "EN_HALF_DOZEN": dict(lang="any", script="latin", groups=()),
    "EN_DOZEN": dict(lang="any", script="latin", groups=()),
    "EN_TWIN_PACK": dict(lang="any", script="latin", groups=()),
    "EN_TRIPLE_PACK": dict(lang="any", script="latin", groups=()),
    "EN_DOUBLE_PACK": dict(lang="any", script="latin", groups=()),
    "EN_COUNT_NUM_NOUN": dict(lang="any", script="latin"),
    "EN_COUNT_NOUN_TRAIL": dict(lang="any", script="latin"),
    # count_pack/latin_cpi (extra_count, script=None)
    "NUM_ROLLS": dict(lang="any"),
    "EN_COMMA_XN": dict(lang="any"),
    "EN_PCS": dict(lang="any"),
    "EN_APOS_S": dict(lang="any"),
    "EN_N_TICKETS": dict(lang="any"),
    # count_pack/vi + vi_sheets (extra_count, script=None)
    "VI_PIECES": dict(lang="vi"),
    "VI_TO_SHEETS": dict(lang="any"),
}

# extra_count default metadata (count_pack bucket, extract role).
_EXTRA_COUNT_DEFAULT = dict(
    role="extract", kind="extra_count", bucket="count_pack", groups=("count",)
)


def _build(id_):
    meta = dict(_META[id_])
    if id_ == "VALUE_UNIT":
        regex = _value_unit_regex()
    elif id_ in ("CENTILITRE", "LITRE_VI"):
        e = _PB["extra_unit"][id_]
        regex = re.compile(e["regex"])
        meta["unit_emit"] = UnitEmit(basis=e["basis"], su=e["su"], mul=float(e["mul"]))
    elif id_ in ("NUM_X_VALUE_UNIT", "VALUE_UNIT_X_NUM"):
        regex = _pack_regex(_PB["pack"][id_]["form"])
    elif id_ in _PB["basis_markers"]:
        b = _PB["basis_markers"][id_]
        regex = re.compile(b["regex"])
        meta["pricing_basis_emit"] = b["basis"]
    else:  # C-class count noun (canon count carries full meta; extra_count doesn't)
        spec = _COUNTS[id_]
        regex = _count_regex(spec)
        if "kind" not in meta:  # extra_count id — fill count_pack bucket defaults
            merged = dict(_EXTRA_COUNT_DEFAULT)
            merged.update(meta)
            meta = merged
        if "fixed_count" in spec:
            meta["fixed_count"] = int(spec["fixed_count"])
    return PackPattern(id=id_, regex=regex, **meta)


def build_ids(*ids):
    return tuple(_build(i) for i in ids)
